#!/usr/bin/env python3
"""The reported sample's own genotype, as MAF columns.

    sample_genotypes.py --maf in.maf --output out.maf

The MAF carries the sample's FORMAT values as two raw strings, FORMAT_FIELDS ("GT:AD:DP:GQ") and
FORMAT_VALUES ("0/1:12,9:21:99"), from the VCF that VEP annotated. This step reads them into:

  Zygosity     heterozygous / homozygous / hemizygous (one allele called) / "." (no call)
  Sample_GT    the genotype as called ("0/1", "1|1", "1")
  Sample_DP    read depth at the site in this sample
  Sample_GQ    genotype quality
  Sample_AD    allele depths, reference first ("12,9")
  Sample_VAF   alternate reads / all reads, from AD (two decimals)

Missing FORMAT fields give ".". In cohort mode (--blank) every column is ".": no member is the
sample, and each member's genotype is in GT_<sample> or the genotype sidecar. The INFO field is
not used: in a joint-called VCF its AC, AN and DP describe every sample of the call set together.
"""

import argparse
import re
import sys

COLUMNS = ["Zygosity", "Sample_GT", "Sample_DP", "Sample_GQ", "Sample_AD", "Sample_VAF"]
MISSING = "."
SPLIT_GT = re.compile(r"[/|]")


def zygosity(gt):
    alleles = [a for a in SPLIT_GT.split(gt) if a not in (".", "")]
    if not alleles or all(a == "0" for a in alleles):
        return MISSING
    if len(alleles) == 1:
        return "hemizygous"
    return "homozygous" if len(set(alleles)) == 1 else "heterozygous"


def vaf(ad):
    try:
        depths = [int(x) for x in ad.split(",")]
    except ValueError:
        return MISSING
    total = sum(depths)
    return f"{sum(depths[1:]) / total:.2f}" if total and len(depths) > 1 else MISSING


def genotype(fields, values):
    """Columns for one FORMAT_FIELDS / FORMAT_VALUES pair."""
    if fields in ("", MISSING, "NA") or values in ("", MISSING, "NA"):
        return [MISSING] * len(COLUMNS)
    f = dict(zip(fields.split(":"), values.split(":")))
    clean = lambda k: f.get(k, MISSING) if f.get(k, MISSING) not in ("", ".") else MISSING
    gt, ad = clean("GT"), clean("AD")
    return [zygosity(gt) if gt != MISSING else MISSING, gt, clean("DP"), clean("GQ"), ad,
            vaf(ad) if ad != MISSING else MISSING]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--maf", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--blank", action="store_true", help="cohort mode: every column '.'")
    args = ap.parse_args()

    with open(args.maf, newline="\n") as fin, open(args.output, "w", newline="\n") as fout:
        header = fin.readline().rstrip("\n").split("\t")
        col = {}
        for i, name in enumerate(header):
            col.setdefault(name, i)
        if "FORMAT_FIELDS" not in col or "FORMAT_VALUES" not in col:
            sys.exit(f"{args.maf}: no FORMAT_FIELDS / FORMAT_VALUES columns")
        i_f, i_v = col["FORMAT_FIELDS"], col["FORMAT_VALUES"]
        fout.write("\t".join(header + COLUMNS) + "\n")
        counts = {}
        for line in fin:
            r = line.rstrip("\n").split("\t")
            g = [MISSING] * len(COLUMNS) if args.blank else genotype(r[i_f], r[i_v])
            counts[g[0]] = counts.get(g[0], 0) + 1
            fout.write("\t".join(r + g) + "\n")
    print(f"{args.output}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
          file=sys.stderr)


if __name__ == "__main__":
    main()
