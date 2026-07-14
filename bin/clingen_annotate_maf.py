#!/usr/bin/env python3
"""
MuSA — clingen_annotate_maf.py

Gene-level ClinGen annotation of a MAF, keyed by Hugo_Symbol. Joins four
authoritative ClinGen gene tables and writes/overwrites these columns:

  overwrite (already present from dbNSFP, now authoritative):
      ClinGen_Haploinsufficiency_Score, ClinGen_Haploinsufficiency_Description
  add:
      ClinGen_Triplosensitivity_Score, ClinGen_Triplosensitivity_Description
      ClinGen_GeneDisease_Classification, ClinGen_GeneDisease_MOI, ClinGen_GeneDisease_Disease
      ClinGen_Actionability_Adult, ClinGen_Actionability_Pediatric

P(HI) is left untouched (DECIPHER pHaplo — a different metric, not in the ClinGen
dosage file). Genes absent from a source get NA. Overwrite-in-place means no
duplicate columns are created.

Dosage scores: ClinGen uses 0-3 as evidence levels; the codes 30 (gene associated
with autosomal-recessive phenotype) and 40 (dosage sensitivity unlikely) are NOT
haploinsufficiency evidence. They are emitted as NA in the numeric *Score* column
(so ARGUS's `HI >= 2` threshold never mis-fires) with the meaning kept in *Description*.
"""

from __future__ import annotations

import argparse
import csv
import sys

NA = "NA"

# Dosage codes that are not 0-3 evidence levels → NA score, explanatory text.
_DOSAGE_CODE_TEXT = {
    "30": "Gene associated with autosomal recessive phenotype",
    "40": "Dosage sensitivity unlikely",
}

# Gene-disease validity classification strength (strongest wins when a gene has
# several disease curations).
_VALIDITY_RANK = {
    "definitive": 6, "strong": 5, "moderate": 4, "limited": 3,
    "disputed": 2, "refuted": 1,
    "no known disease relationship": 0, "animal model only": 0,
}


def _find_header_row(path, needles, sep):
    """Return (skiprows, header_fields) for the first line containing all needle
    substrings (case-insensitive). Handles ClinGen files with comment preambles."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            low = line.lower()
            if all(n in low for n in needles):
                header = next(csv.reader([line.rstrip("\n")], delimiter=sep))
                header = [h.lstrip("#").strip() for h in header]
                return i, header
    raise ValueError(f"{path}: no header row matching {needles}")


def _rows(path, skiprows, sep):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for _ in range(skiprows + 1):
            next(fh, None)
        for rec in csv.reader(fh, delimiter=sep):
            if rec:
                yield rec


def _col(header, *needles):
    """Index of the first header column containing all needle substrings (ci), or None."""
    for i, h in enumerate(header):
        low = h.lower()
        if all(n in low for n in needles):
            return i
    return None


def _get(rec, idx):
    if idx is None or idx >= len(rec):
        return ""
    return rec[idx].strip()


def _junk_gene(gene: str) -> bool:
    """Skip empty rows and ClinGen separator lines (e.g. '+++++' under the header)."""
    return not gene or gene.strip("+") == ""


def load_dosage(path):
    """gene -> (hi_score, hi_desc, ts_score, ts_desc)."""
    skip, header = _find_header_row(path, ["gene symbol", "haploinsufficiency"], "\t")
    g_i  = _col(header, "gene symbol")
    hs_i = _col(header, "haploinsufficiency", "score")
    hd_i = _col(header, "haploinsufficiency", "description")
    ts_i = _col(header, "triplosensitivity", "score")
    td_i = _col(header, "triplosensitivity", "description")
    out = {}
    for rec in _rows(path, skip, "\t"):
        gene = _get(rec, g_i).upper()
        if _junk_gene(gene):
            continue
        out[gene] = (
            *_norm_dosage(_get(rec, hs_i), _get(rec, hd_i)),
            *_norm_dosage(_get(rec, ts_i), _get(rec, td_i)),
        )
    return out


def _norm_dosage(score, desc):
    """(score, desc) → numeric 0-3 score or NA (+ explanatory desc for codes 30/40)."""
    s = score.strip()
    if s in ("0", "1", "2", "3"):
        return s, (desc or NA)
    if s in _DOSAGE_CODE_TEXT:
        return NA, (desc or _DOSAGE_CODE_TEXT[s])
    return NA, (desc or NA)


def load_validity(path):
    """gene -> (classification, moi, disease) keeping the strongest classification."""
    skip, header = _find_header_row(path, ["gene symbol", "classification"], ",")
    g_i = _col(header, "gene symbol")
    c_i = _col(header, "classification")
    m_i = _col(header, "moi")
    d_i = _col(header, "disease label") or _col(header, "disease")
    best = {}
    for rec in _rows(path, skip, ","):
        gene = _get(rec, g_i).upper()
        cls = _get(rec, c_i)
        if _junk_gene(gene) or not cls:
            continue
        rank = _VALIDITY_RANK.get(cls.lower(), -1)
        cur = best.get(gene)
        if cur is None or rank > cur[0]:
            best[gene] = (rank, cls, _get(rec, m_i), _get(rec, d_i))
    return {g: (v[1], v[2] or NA, v[3] or NA) for g, v in best.items()}


def load_actionability(path):
    """gene -> assertion/outcome string (distinct disease:assertion joined).
    Tolerant of the exact ClinGen actionability TSV header."""
    if path is None:
        return {}
    skip, header = _find_header_row(path, ["gene"], "\t")
    g_i = _col(header, "gene", "symbol") or _col(header, "gene")
    # Pick the most assertion-like column available.
    a_i = (_col(header, "assertion") or _col(header, "actionability")
           or _col(header, "total", "score") or _col(header, "score"))
    d_i = _col(header, "disease")
    agg = {}
    for rec in _rows(path, skip, "\t"):
        gene = _get(rec, g_i).upper()
        val = _get(rec, a_i)
        if _junk_gene(gene) or not val:
            continue
        disease = _get(rec, d_i)
        label = f"{disease}: {val}" if disease else val
        agg.setdefault(gene, [])
        if label not in agg[gene]:
            agg[gene].append(label)
    return {g: " | ".join(v) for g, v in agg.items()}


# Output column name -> (source dict, tuple index or None for scalar dicts)
def annotate(maf_in, maf_out, dosage, validity, act_adult, act_ped, gene_col):
    with open(maf_in, encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        try:
            g_idx = header.index(gene_col)
        except ValueError:
            sys.exit(f"ERROR: gene column '{gene_col}' not in MAF header")

        # Columns this step manages: name -> function(gene) -> value.
        def hi_score(g):  return dosage.get(g, (NA, NA, NA, NA))[0]
        def hi_desc(g):   return dosage.get(g, (NA, NA, NA, NA))[1]
        def ts_score(g):  return dosage.get(g, (NA, NA, NA, NA))[2]
        def ts_desc(g):   return dosage.get(g, (NA, NA, NA, NA))[3]
        def gd_class(g):  return validity.get(g, (NA, NA, NA))[0]
        def gd_moi(g):    return validity.get(g, (NA, NA, NA))[1]
        def gd_dis(g):    return validity.get(g, (NA, NA, NA))[2]
        def act_a(g):     return act_adult.get(g, NA)
        def act_p(g):     return act_ped.get(g, NA)

        managed = [
            ("ClinGen_Haploinsufficiency_Score", hi_score),
            ("ClinGen_Haploinsufficiency_Description", hi_desc),
            ("ClinGen_Triplosensitivity_Score", ts_score),
            ("ClinGen_Triplosensitivity_Description", ts_desc),
            ("ClinGen_GeneDisease_Classification", gd_class),
            ("ClinGen_GeneDisease_MOI", gd_moi),
            ("ClinGen_GeneDisease_Disease", gd_dis),
            ("ClinGen_Actionability_Adult", act_a),
            ("ClinGen_Actionability_Pediatric", act_p),
        ]

        # Overwrite existing columns in place; append genuinely new ones.
        col_idx = {}          # managed name -> existing index (or None → appended)
        out_header = list(header)
        appended = []
        for name, _ in managed:
            if name in header:
                col_idx[name] = header.index(name)
            else:
                col_idx[name] = None
                appended.append(name)
        out_header += appended

        with open(maf_out, "w", encoding="utf-8", newline="") as out:
            writer = csv.writer(out, delimiter="\t", lineterminator="\n")
            writer.writerow(out_header)
            n = 0
            for row in reader:
                if len(row) < len(header):
                    row = row + [""] * (len(header) - len(row))
                gene = row[g_idx].strip().upper()
                extra = {name: fn(gene) for name, fn in managed}
                for name, idx in col_idx.items():
                    if idx is not None:
                        row[idx] = extra[name]
                row = row + [extra[name] for name in appended]
                writer.writerow(row)
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description="Gene-level ClinGen MAF annotation.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--dosage", required=True, help="ClinGen_gene_curation_list_GRCh38.tsv")
    ap.add_argument("--gene-disease", required=True, help="ClinGen gene-validity CSV")
    ap.add_argument("--actionability-adult", default=None)
    ap.add_argument("--actionability-pediatric", default=None)
    ap.add_argument("--gene-col", default="Hugo_Symbol")
    args = ap.parse_args()

    dosage   = load_dosage(args.dosage)
    validity = load_validity(args.gene_disease)
    act_a    = load_actionability(args.actionability_adult)
    act_p    = load_actionability(args.actionability_pediatric)
    print(f"[INFO] ClinGen: {len(dosage)} dosage, {len(validity)} validity, "
          f"{len(act_a)} act-adult, {len(act_p)} act-pediatric genes", file=sys.stderr)

    n = annotate(args.input, args.output, dosage, validity, act_a, act_p, args.gene_col)
    print(f"[INFO] annotated {n} MAF rows -> {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
