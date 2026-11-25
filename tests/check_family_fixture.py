#!/usr/bin/env python3
"""Check a family-fixture MAF: every member's genotype, the proband's, and the family facts.

    check_family_fixture.py --maf FAM.raw.maf --vcf family_fixture.vcf.gz

Genotypes are checked against the fixture VCF by sample NAME, so a member given another member's
column (the bug GATK's sample reordering caused before MuSA 1.7) fails whatever the column order.
Inheritance and its check are compared with the outcome each fixture site was written to produce.
Exits non-zero on any mismatch. Works for -profile test_family and test_family_sarek.
"""

import argparse
import csv
import gzip
import sys

PROBAND = "P1"
# (chrom, pos): (Inheritance, Inheritance_check), as the fixture was designed (male proband P1,
# mother M1, father F1; chrX outside PAR1 is hemizygous in P1 and F1).
EXPECTED = {
    ("chr22", "22514169"): ("biparental", "pass"),
    ("chr22", "22514173"): ("unknown", "mendelian_error"),
    ("chr22", "22514449"): ("unknown", "parent_no_call"),
    ("chr22", "22514452"): ("not_in_proband", "pass"),
    ("chr22", "37723206"): ("de_novo", "pass"),
    ("chr22", "37723862"): ("maternal", "pass"),
    ("chr22", "37725145"): ("paternal", "pass"),
    ("chr22", "37726115"): ("unknown", "both_parents_carry"),
    ("chr22", "50090140"): ("unknown", "parent_low_depth"),
    ("chr22", "50090194"): ("unknown", "parent_alt_reads"),
    ("chr22", "50092072"): ("unknown", "proband_allele_balance"),
    ("chrX", "1190963"): ("paternal", "pass"),
    ("chrX", "100594020"): ("maternal", "pass"),
    ("chrX", "100678157"): ("de_novo", "pass"),
    ("chrX", "100686708"): ("unknown", "parent_no_call"),
}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--maf", required=True)
    ap.add_argument("--vcf", required=True)
    args = ap.parse_args()

    vcf = {}
    with gzip.open(args.vcf, "rt") as fh:
        for line in fh:
            if line.startswith("##"):
                continue
            f = line.rstrip("\n").split("\t")
            if line.startswith("#CHROM"):
                samples = f[9:]
                continue
            keys = f[8].split(":")
            vcf[(f[0], f[1])] = {s: dict(zip(keys, v.split(":"))) for s, v in zip(samples, f[9:])}

    csv.field_size_limit(10**9)
    with open(args.maf) as fh:
        r = csv.reader(fh, delimiter="\t")
        header = next(r)
        col = {}
        for i, n in enumerate(header):
            col.setdefault(n, i)
        rows = list(r)

    errors = []
    seen = set()
    for row in rows:
        site = (row[col["Chromosome"]], row[col["Start_Position"]])
        seen.add(site)
        calls = vcf.get(site)
        if calls is None:
            errors.append(f"{site}: not in the fixture VCF")
            continue
        for s, call in calls.items():
            for fmt in ("GT", "DP", "AD"):
                got = row[col[f"{fmt}_{s}"]]
                want = call.get(fmt, ".")
                if got != want:
                    errors.append(f"{site}: {fmt}_{s} = {got}, the VCF has {want}")
        if row[col["Sample_GT"]] != calls[PROBAND]["GT"]:
            errors.append(f"{site}: Sample_GT = {row[col['Sample_GT']]}, proband {PROBAND} has "
                          f"{calls[PROBAND]['GT']}")
        got = (row[col["Inheritance"]], row[col["Inheritance_check"]])
        if site in EXPECTED and got != EXPECTED[site]:
            errors.append(f"{site}: Inheritance {got}, expected {EXPECTED[site]}")
    for site in EXPECTED:
        if site not in seen:
            errors.append(f"{site}: missing from the MAF")

    for e in errors:
        print(e, file=sys.stderr)
    print(f"{args.maf}: {len(rows)} variants, {len(errors)} mismatches", file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
