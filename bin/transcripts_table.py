#!/usr/bin/env python3
"""Every transcript of every variant, as a table next to the MAF.

    transcripts_table.py --vep transcripts.vep.vcf --maf patient.maf [--dbnsfp dbnsfp_transcripts.tsv.gz]
                         --output patient.transcripts.tsv.gz

The MAF reports each variant on one transcript (VEP's pick). This table lists all of them, keyed
like the MAF (Chromosome, Start_Position, Reference_Allele, Tumor_Seq_Allele2), so a reader, the
report or SIDEVAR can show the variant on the transcript they want, MANE Select first:

  MuSA_pick        yes for the transcript the MAF row reports, else no
  Feature ... PolyPhen   VEP's transcript-level fields (see VEP_TRANSCRIPTS)
  SIFT_score ...         with --dbnsfp, dbNSFP's scores and predictions for that transcript, named as
                         in the MAF (where they are one value per variant, on the MANE transcript)

dbNSFP keeps a transcript's values as one element of ';'-separated lists aligned with
Ensembl_transcriptid; the element at the transcript's position is written on its line, "." when
dbNSFP has no record for the transcript (dbNSFP covers non-synonymous changes only).

Transcripts are ordered: MANE Select, MANE Plus Clinical, the MAF's pick, Ensembl canonical, then
by impact. Only transcript features are kept (no regulatory or motif features).

VCF and MAF positions differ for indels: vcf2maf drops the base an indel's REF and ALT share and
moves the start past it for a deletion. Every VCF record must land on a MAF row; the run stops if
one does not, rather than writing a table nobody can join.
"""

import argparse
import gzip
import os
import sys

MAF_KEY = ["Chromosome", "Start_Position", "Reference_Allele", "Tumor_Seq_Allele2"]
IMPACT_RANK = {"HIGH": 0, "MODERATE": 1, "LOW": 2, "MODIFIER": 3}
OUT_FIELDS = ["Feature", "SYMBOL", "Gene", "BIOTYPE", "Consequence", "IMPACT", "HGVSc", "HGVSp",
              "EXON", "INTRON", "cDNA_position", "CDS_position", "Protein_position",
              "Amino_acids", "Codons", "STRAND", "FLAGS", "CANONICAL", "MANE_SELECT",
              "MANE_PLUS_CLINICAL", "TSL", "APPRIS", "CCDS", "ENSP", "SWISSPROT", "SIFT",
              "PolyPhen"]
MISSING = "."
# VEP --total_length writes these as position/length: the position stays in its column, the length
# goes to a column of its own, after every other column.
LENGTH_OF = {"cDNA_position": "cDNA_length", "CDS_position": "CDS_length",
             "Protein_position": "Protein_length"}
LENGTH_FIELDS = list(LENGTH_OF.values())


def split_lengths(v):
    """Move VEP's total lengths out of the position fields of one CSQ entry; return the lengths."""
    lengths = []
    for pos in LENGTH_OF:
        parts = v.get(pos, "").split("/")
        if len(parts) == 2:
            v[pos] = "" if parts[0] == "-" else parts[0]
            lengths.append(parts[1] or MISSING)
        else:
            lengths.append(MISSING)
    return lengths


def maf_key(chrom, pos, ref, alt):
    """vcf2maf's coordinates for a biallelic VCF record."""
    pos = int(pos)
    if len(ref) != len(alt) and ref[:1] == alt[:1]:
        ref, alt = ref[1:], alt[1:]
        if ref:          # deletion (or a complex change): starts after the shared base
            pos += 1
    return (chrom, str(pos), ref or "-", alt or "-")


def load_dbnsfp(path):
    """(score columns, {VCF key: {transcript: [value per column]}}) from MERGE_ANNOTATIONS."""
    values = {}
    with gzip.open(path, "rt") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        if "Ensembl_transcriptid" not in header:     # basic mode: no dbNSFP, header only
            return [], values
        tid = header.index("Ensembl_transcriptid")
        cols = [i for i in range(1, len(header)) if i != tid]
        for line in fh:
            r = line.rstrip("\n").split("\t")
            tx = r[tid].split(";")
            lists = []
            for i in cols:
                items = r[i].split(";")
                # A list shorter or longer than the transcript list cannot be indexed by it.
                lists.append(items if len(items) == len(tx) else [MISSING] * len(tx))
            per_tx = values.setdefault(r[0], {})
            for j, t in enumerate(tx):
                if t and t != MISSING and t not in per_tx:
                    per_tx[t] = [(lst[j] or MISSING) for lst in lists]
    return [header[i] for i in cols], values


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vep", required=True)
    ap.add_argument("--maf", required=True)
    ap.add_argument("--dbnsfp", help="MERGE_ANNOTATIONS' dbnsfp_transcripts.tsv.gz: VCF key, "
                    "Ensembl_transcriptid and per-transcript score lists")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.maf) as fh:
        header = fh.readline().rstrip("\n").split("\t")
        col = {}
        for i, n in enumerate(header):
            col.setdefault(n, i)
        picks = {}
        for line in fh:
            r = line.rstrip("\n").split("\t")
            picks[tuple(r[col[k]] for k in MAF_KEY)] = r[col["Feature"]] if "Feature" in col else ""

    db_fields, db_values = load_dbnsfp(args.dbnsfp) if args.dbnsfp else ([], {})

    # Lines are written as they are made (about 25 per variant: 2 million for an exome), into a
    # temporary file renamed at the end, so a run that stops on an unmatched variant leaves no table.
    tmp = args.output + ".partial"
    csq = None
    unmatched, n_records, n_rows, with_scores = [], 0, 0, 0
    with_pick = set()
    with open(args.vep) as fh, gzip.open(tmp, "wt") as out:
        out.write("\t".join(MAF_KEY + ["MuSA_pick"] + OUT_FIELDS + db_fields + LENGTH_FIELDS) + "\n")
        for line in fh:
            if line.startswith("##INFO=<ID=CSQ"):
                csq = line.split("Format: ")[1].rstrip('">\n').split("|")
                continue
            if line.startswith("#"):
                continue
            n_records += 1
            f = line.rstrip("\n").split("\t")
            key = maf_key(f[0], f[1], f[3], f[4])
            scores = db_values.get("|".join(f[:2] + f[3:5]), {})
            no_scores = [MISSING] * len(db_fields)
            if key not in picks:
                unmatched.append(":".join(f[:2] + f[3:5]))
                continue
            entries = []
            for item in f[7].split(";"):
                if item.startswith("CSQ="):
                    for e in item[4:].split(","):
                        v = dict(zip(csq, e.split("|")))
                        if v.get("Feature_type") == "Transcript":
                            entries.append(v)
            for v in entries:
                v["MuSA_pick"] = "yes" if v.get("Feature") == picks[key] else "no"
            entries.sort(key=lambda v: (v.get("MANE_SELECT", "") == "",
                                        v.get("MANE_PLUS_CLINICAL", "") == "",
                                        v["MuSA_pick"] != "yes",
                                        v.get("CANONICAL", "") != "YES",
                                        min(IMPACT_RANK.get(i, 4) for i in v.get("IMPACT", "").split("&"))))
            for v in entries:
                # "&" joins a field's values in VEP output; "%3D" is VEP's URL-encoded "=" in a
                # synonymous HGVSp, decoded in the MAF too (CLEAN_COLUMNS).
                tx_scores = scores.get(v.get("Feature", ""), no_scores)
                lengths = split_lengths(v)
                out.write("\t".join(list(key) + [v["MuSA_pick"]] +
                                     [(v.get(k, "") or MISSING).replace("&", ",").replace("%3D", "=")
                                      for k in OUT_FIELDS] + tx_scores + lengths) + "\n")
                n_rows += 1
                with_scores += any(x != MISSING for x in tx_scores)
                if v["MuSA_pick"] == "yes":
                    with_pick.add(key)

    if csq is None or unmatched:
        os.remove(tmp)
    if csq is None:
        sys.exit(f"{args.vep}: no CSQ header")
    if unmatched:
        sys.exit(f"{len(unmatched)} of {n_records} variants have no MAF row under vcf2maf "
                 f"coordinates, e.g. {', '.join(unmatched[:5])}")

    os.replace(tmp, args.output)
    print(f"{args.output}: {n_rows} transcripts for {n_records} variants; the MAF's transcript "
          f"found for {len(with_pick)}; dbNSFP scores on {with_scores} transcripts", file=sys.stderr)

if __name__ == "__main__":
    main()
