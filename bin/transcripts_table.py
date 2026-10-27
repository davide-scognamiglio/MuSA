#!/usr/bin/env python3
"""Every transcript of every variant, as a table next to the MAF.

    transcripts_table.py --vep transcripts.vep.vcf --maf patient.maf --output patient.transcripts.tsv.gz

The MAF reports each variant on one transcript (VEP's pick). This table lists all of them, keyed
like the MAF (Chromosome, Start_Position, Reference_Allele, Tumor_Seq_Allele2), so a reader, the
report or SIDEVAR can show the variant on the transcript they want, MANE Select first:

  MuSA_pick        yes for the transcript the MAF row reports, else no
  Feature ... PolyPhen   VEP's transcript-level fields (see VEP_TRANSCRIPTS)

Transcripts are ordered: MANE Select, MANE Plus Clinical, the MAF's pick, Ensembl canonical, then
by impact. Only transcript features are kept (no regulatory or motif features).

VCF and MAF positions differ for indels: vcf2maf drops the base an indel's REF and ALT share and
moves the start past it for a deletion. Every VCF record must land on a MAF row; the run stops if
one does not, rather than writing a table nobody can join.
"""

import argparse
import gzip
import sys

MAF_KEY = ["Chromosome", "Start_Position", "Reference_Allele", "Tumor_Seq_Allele2"]
IMPACT_RANK = {"HIGH": 0, "MODERATE": 1, "LOW": 2, "MODIFIER": 3}
OUT_FIELDS = ["Feature", "SYMBOL", "Gene", "BIOTYPE", "Consequence", "IMPACT", "HGVSc", "HGVSp",
              "EXON", "INTRON", "cDNA_position", "CDS_position", "Protein_position",
              "Amino_acids", "Codons", "STRAND", "FLAGS", "CANONICAL", "MANE_SELECT",
              "MANE_PLUS_CLINICAL", "TSL", "APPRIS", "CCDS", "ENSP", "SWISSPROT", "SIFT",
              "PolyPhen"]
MISSING = "."


def maf_key(chrom, pos, ref, alt):
    """vcf2maf's coordinates for a biallelic VCF record."""
    pos = int(pos)
    if len(ref) != len(alt) and ref[:1] == alt[:1]:
        ref, alt = ref[1:], alt[1:]
        if ref:          # deletion (or a complex change): starts after the shared base
            pos += 1
    return (chrom, str(pos), ref or "-", alt or "-")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vep", required=True)
    ap.add_argument("--maf", required=True)
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

    csq = None
    rows, unmatched, n_records = [], [], 0
    with open(args.vep) as fh:
        for line in fh:
            if line.startswith("##INFO=<ID=CSQ"):
                csq = line.split("Format: ")[1].rstrip('">\n').split("|")
                continue
            if line.startswith("#"):
                continue
            n_records += 1
            f = line.rstrip("\n").split("\t")
            key = maf_key(f[0], f[1], f[3], f[4])
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
                rows.append(list(key) + [v["MuSA_pick"]] +
                            [(v.get(k, "") or MISSING).replace("&", ",").replace("%3D", "=")
                             for k in OUT_FIELDS])

    if csq is None:
        sys.exit(f"{args.vep}: no CSQ header")
    if unmatched:
        sys.exit(f"{len(unmatched)} of {n_records} variants have no MAF row under vcf2maf "
                 f"coordinates, e.g. {', '.join(unmatched[:5])}")

    with gzip.open(args.output, "wt") as out:
        out.write("\t".join(MAF_KEY + ["MuSA_pick"] + OUT_FIELDS) + "\n")
        for r in rows:
            out.write("\t".join(r) + "\n")
    with_pick = len({tuple(r[:4]) for r in rows if r[4] == "yes"})
    print(f"{args.output}: {len(rows)} transcripts for {n_records} variants; the MAF's transcript "
          f"found for {with_pick}", file=sys.stderr)


if __name__ == "__main__":
    main()
