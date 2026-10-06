#!/usr/bin/env python3
"""ClinVar evidence at the same amino-acid residue: the ACMG criteria PS1 and PM5.

    clinvar_residues.py build    variant_summary_2026-07.txt.gz clinvar_residues.tsv.gz
    clinvar_residues.py annotate --maf in.maf --index clinvar_residues.tsv.gz --output out.maf

PS1: the same amino-acid change is established pathogenic in ClinVar, reached by a DIFFERENT
nucleotide change (the very same nucleotide change is the variant's own ClinVar record, PP5, and
the MAF already carries it in CLNSIG). PM5: a different missense change at the same residue is
established pathogenic. Neither can be read off one MAF row: both need every other ClinVar
variant at that residue. VEP's SameCodon plugin answers it through a database round-trip per
variant (an exome would take days), so the residues are indexed once, at setup, from ClinVar's
variant_summary (the VCF carries no protein change).

Adapted from ARGUS (ARGUS/clinvar_index.py, MIT licence, same author). The residue is anchored
on genomic coordinates, so transcript numbering differences between ClinVar and the MAF neither
hide nor invent a match: every genomic position covered by a pathogenic missense of a
(gene, residue) group points to that group, and the query matches by landing on one of those
positions with the same reference amino acid. A residue ClinVar knows from a single variant at a
different codon base falls back to gene + protein position, guarded by the reference amino acid
and by that variant lying within the query's codon (2 bp).

Thresholds follow ARGUS: PS1 needs a record with at least 2 review stars, PM5 at least 1.
PM5 is not reported when PS1 is (the change itself is established pathogenic). Low-penetrance and
risk-factor assertions are kept but labelled, since they are weaker evidence.

Adds two MAF columns, "." when nothing applies (and on every non-missense row):
    ClinVar_PS1  e.g. "R978C 2★ via 17:7676154 G>T"
    ClinVar_PM5  e.g. "R978H 3★; R978S 1★ (low penetrance)"
"""

import argparse
import csv
import gzip
import os
import re
import sys

PS1_MIN_STARS = 2
PM5_MIN_STARS = 1

# variant_summary.txt.gz columns used, checked against the header at build time.
COLUMNS = {
    "Name": 2, "GeneSymbol": 4, "ClinicalSignificance": 6, "Assembly": 16,
    "Chromosome": 18, "ReviewStatus": 24, "PositionVCF": 31,
    "ReferenceAlleleVCF": 32, "AlternateAlleleVCF": 33,
}

AA3_TO_1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E",
    "Gly": "G", "His": "H", "Ile": "I", "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F",
    "Pro": "P", "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
}
# A single-residue missense: "(p.Arg978Cys)" in ClinVar's Name, "p.Arg978Cys" in HGVSp_VEP.
MISSENSE = re.compile(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})(?:\)|$)")

REVIEW_STARS = {
    "practice guideline": 4,
    "reviewed by expert panel": 3,
    "criteria provided, multiple submitters, no conflicts": 2,
    "criteria provided, conflicting classifications": 1,
    "criteria provided, conflicting interpretations": 1,
    "criteria provided, single submitter": 1,
}

INDEX_HEADER = ["chrom", "pos", "ref", "alt", "gene", "aa_pos", "aa_ref", "aa_alt",
                "stars", "low_penetrance"]


def norm_chrom(c):
    c = c.strip()
    if c[:3].lower() == "chr":
        c = c[3:]
    c = c.upper()
    return "MT" if c == "M" else c


def missense(text):
    """(aa_ref, aa_pos, aa_alt) in one-letter codes, or None if not a clean missense."""
    m = MISSENSE.search(text or "")
    if not m:
        return None
    ref, alt = AA3_TO_1.get(m.group(1)), AA3_TO_1.get(m.group(3))
    if ref is None or alt is None or ref == alt:
        return None
    return ref, int(m.group(2)), alt


# ── build ─────────────────────────────────────────────────────────────────────────────────────────
def build(args):
    """Keep pathogenic, single-residue missense SNVs on GRCh38, one row per ClinVar variant."""
    rows = {}
    with gzip.open(args.summary, "rt", encoding="utf-8", errors="replace") as fh:
        header = next(fh).rstrip("\n").split("\t")
        for name, i in COLUMNS.items():
            if i >= len(header) or header[i] != name:
                sys.exit(f"variant_summary column {i} is not '{name}': the format changed")
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) <= COLUMNS["AlternateAlleleVCF"] or f[COLUMNS["Assembly"]] != "GRCh38":
                continue
            sig = f[COLUMNS["ClinicalSignificance"]].lower()
            if "pathogenic" not in sig or "conflicting" in sig:
                continue
            aa = missense(f[COLUMNS["Name"]])
            gene = f[COLUMNS["GeneSymbol"]].strip().upper()
            pos = f[COLUMNS["PositionVCF"]]
            ref = f[COLUMNS["ReferenceAlleleVCF"]].upper()
            alt = f[COLUMNS["AlternateAlleleVCF"]].upper()
            if (aa is None or not gene or gene == "-" or not pos.isdigit()
                    or len(ref) != 1 or len(alt) != 1 or ref not in "ACGT" or alt not in "ACGT"):
                continue
            stars = REVIEW_STARS.get(f[COLUMNS["ReviewStatus"]].strip().lower(), 0)
            low = int("low penetrance" in sig or "risk factor" in sig)
            key = (norm_chrom(f[COLUMNS["Chromosome"]]), int(pos), ref, alt, gene, aa)
            # One variant can have several records (e.g. one per gene); keep the strongest.
            prev = rows.get(key)
            if prev is None or (stars, -low) > (prev[0], -prev[1]):
                rows[key] = (stars, low)

    with gzip.open(args.output, "wt", newline="") as out:
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
        w.writerow(INDEX_HEADER)
        for (chrom, pos, ref, alt, gene, (aa_ref, aa_pos, aa_alt)), (stars, low) in sorted(rows.items()):
            w.writerow([chrom, pos, ref, alt, gene, aa_pos, aa_ref, aa_alt, stars, low])
    print(f"{args.output}: {len(rows)} pathogenic missense SNVs")


# ── annotate ──────────────────────────────────────────────────────────────────────────────────────
class Residues:
    """The index, grouped by residue and reachable by genomic footprint or gene + position."""

    def __init__(self, path):
        groups = {}   # (gene, aa_pos, aa_ref) -> {aa_alt: [(stars, low, chrom, pos, ref, alt)]}
        footprint = {}
        with gzip.open(path, "rt") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                gkey = (r["gene"], int(r["aa_pos"]), r["aa_ref"])
                rec = (int(r["stars"]), int(r["low_penetrance"]), r["chrom"], int(r["pos"]),
                       r["ref"], r["alt"])
                groups.setdefault(gkey, {}).setdefault(r["aa_alt"], []).append(rec)
                footprint.setdefault((r["chrom"], int(r["pos"])), set()).add(gkey)
        self.groups = groups
        self.footprint = footprint

    def residue(self, chrom, pos, gene, aa_pos, aa_ref):
        """The ClinVar residue group this variant falls in, or None."""
        candidates = [g for g in self.footprint.get((chrom, pos), ()) if g[2] == aa_ref]
        if candidates:
            # Overlapping residues (two genes, rare): the one with the best-reviewed record.
            return self.groups[max(candidates, key=lambda g: best_stars(self.groups[g]))]
        # Fallback: same gene, position and reference amino acid, but only if a ClinVar variant of
        # that residue lies within the query's codon (2 bp). Without that check, a protein
        # position read on another transcript matched an unrelated residue: on NA12878, VEP's
        # non-MANE pick made a SGCG variant "p.Leu194Ser" and matched ClinVar's L194S 3.7 kb away.
        alts = self.groups.get((gene, aa_pos, aa_ref))
        if alts and any(r[2] == chrom and abs(r[3] - pos) <= 2 for recs in alts.values() for r in recs):
            return alts
        return None


def best_stars(alts):
    return max(rec[0] for recs in alts.values() for rec in recs)


def label(aa_ref, aa_pos, aa_alt, stars, low):
    return f"{aa_ref}{aa_pos}{aa_alt} {stars}★" + (" (low penetrance)" if low else "")


def evidence(index, chrom, pos, ref, alt, gene, aa):
    aa_ref, aa_pos, aa_alt = aa
    alts = index.residue(chrom, pos, gene, aa_pos, aa_ref)
    if not alts:
        return ".", "."
    # PS1: the same residue change from a different nucleotide change.
    same = [r for r in alts.get(aa_alt, ()) if (r[2], r[3], r[4], r[5]) != (chrom, pos, ref, alt)
            and r[0] >= PS1_MIN_STARS]
    if same:
        s = max(same, key=lambda r: (r[0], -r[1]))
        return (label(aa_ref, aa_pos, aa_alt, s[0], s[1]) + f" via {s[2]}:{s[3]} {s[4]}>{s[5]}",
                ".")
    # PM5: a different residue change, best record of each.
    other = []
    for other_alt, recs in sorted(alts.items()):
        if other_alt == aa_alt:
            continue
        s = max(recs, key=lambda r: (r[0], -r[1]))
        if s[0] >= PM5_MIN_STARS:
            other.append((s[0], label(aa_ref, aa_pos, other_alt, s[0], s[1])))
    pm5 = "; ".join(t for _, t in sorted(other, key=lambda x: -x[0])) or "."
    return ".", pm5


def annotate(args):
    if not os.path.isfile(args.index):
        sys.exit(f"{args.index} not found: this data directory predates MuSA 1.3's ClinVar residue "
                 "index. Run `--workflow setup --update_db_only true` once to add it.")
    index = Residues(args.index)
    with open(args.maf, newline="\n") as fin, open(args.output, "w", newline="\n") as fout:
        header = fin.readline().rstrip("\n").split("\t")
        col = {}
        for i, name in enumerate(header):
            col.setdefault(name, i)
        need = ["Chromosome", "Start_Position", "Reference_Allele", "Tumor_Seq_Allele2",
                "Hugo_Symbol", "HGVSp_VEP"]
        missing = [n for n in need if n not in col]
        if missing:
            sys.exit(f"{args.maf}: missing column(s) {', '.join(missing)}")
        fout.write("\t".join(header + ["ClinVar_PS1", "ClinVar_PM5"]) + "\n")
        n_ps1 = n_pm5 = 0
        for line in fin:
            f = line.rstrip("\n").split("\t")
            ps1 = pm5 = "."
            aa = missense(f[col["HGVSp_VEP"]])
            ref, alt = f[col["Reference_Allele"]].upper(), f[col["Tumor_Seq_Allele2"]].upper()
            pos = f[col["Start_Position"]]
            if aa and len(ref) == 1 and len(alt) == 1 and pos.isdigit():
                ps1, pm5 = evidence(index, norm_chrom(f[col["Chromosome"]]), int(pos), ref, alt,
                                    f[col["Hugo_Symbol"]].upper(), aa)
            n_ps1 += ps1 != "."
            n_pm5 += pm5 != "."
            fout.write("\t".join(f + [ps1, pm5]) + "\n")
    print(f"{args.output}: PS1 evidence on {n_ps1} variants, PM5 on {n_pm5}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("summary")
    b.add_argument("output")
    a = sub.add_parser("annotate")
    a.add_argument("--maf", required=True)
    a.add_argument("--index", required=True)
    a.add_argument("--output", required=True)
    args = ap.parse_args()
    {"build": build, "annotate": annotate}[args.cmd](args)


if __name__ == "__main__":
    main()
