#!/usr/bin/env python3
"""Repeat regions a variant overlaps (UCSC RepeatMasker and Tandem Repeats Finder).

    repeat_regions.py build rmsk.txt.gz simpleRepeat.txt.gz repeat_regions.bed.gz
    repeat_regions.py annotate --maf in.maf --bed repeat_regions.bed.gz --output out.maf

ACMG PM4 is for in-frame indels "in a non-repeat region" and BP3 for in-frame indels "in a
repetitive region without known function": this is the fact those clauses need. MuSA decides no
criterion; it reports which repeats the variant lies in.

build    keeps the RepeatMasker classes that describe tandem or repetitive sequence (Simple_repeat,
         Low_complexity, Satellite; interspersed repeats such as SINE, LINE and LTR are left out)
         and every Tandem Repeats Finder interval (class TRF), as one BED sorted by chromosome and
         start: chrom, start (0-based), end, class.

annotate adds Repeat_region: the classes of every interval the variant overlaps, ';'-separated in
         the order Simple_repeat, Low_complexity, Satellite, TRF, or '.' for none. The variant's
         span is the MAF's Start_Position..End_Position, which vcf2maf sets to the reference bases
         of a substitution or deletion and to the two flanking bases of an insertion.
"""

import argparse
import gzip
import heapq
import os
import shutil
import sys

RMSK_CLASSES = ("Simple_repeat", "Low_complexity", "Satellite")
ORDER = RMSK_CLASSES + ("TRF",)
COLUMNS = ["Repeat_region"]
MISSING = "."


def build(args):
    rows = []
    with gzip.open(args.rmsk, "rt") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            # bin swScore milliDiv milliDel milliIns genoName genoStart genoEnd genoLeft strand
            # repName repClass repFamily ...
            if f[11] in RMSK_CLASSES:
                rows.append((f[5], int(f[6]), int(f[7]), f[11]))
    with gzip.open(args.trf, "rt") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            # bin chrom chromStart chromEnd name ...
            rows.append((f[1], int(f[2]), int(f[3]), "TRF"))
    rows = sorted(set(rows))
    with gzip.open(args.output, "wt") as out:
        for chrom, start, end, cls in rows:
            out.write(f"{chrom}\t{start}\t{end}\t{cls}\n")
    n_trf = sum(r[3] == "TRF" for r in rows)
    print(f"{args.output}: {len(rows)} intervals ({len(rows) - n_trf} RepeatMasker, {n_trf} TRF)",
          file=sys.stderr)


def intervals(path, wanted):
    """(chrom, start, end, class) of the BED, for the chromosomes in `wanted` only."""
    with gzip.open(path, "rt") as fh:
        for line in fh:
            chrom, start, end, cls = line.rstrip("\n").split("\t")
            if chrom in wanted:
                yield chrom, int(start), int(end), cls


def annotate(args):
    # A data directory set up before MuSA 1.7 has no BED. The MAF then goes through without the
    # column rather than with '.', which would claim the variant lies in no repeat: a reader can
    # tell "not annotated" (no column) from "no repeat" ('.').
    if not os.path.isfile(args.bed):
        print(f"[WARN] {args.bed} not found: this data directory predates MuSA 1.7's repeat "
              "regions, so the MAF has no Repeat_region column. Run `--workflow setup "
              "--update_db_only true` once to add them.", file=sys.stderr)
        shutil.copyfile(args.maf, args.output)
        return

    # Two passes over the MAF, so memory does not grow with it: the first keeps each row's span,
    # the second copies every row through with the new column added.
    with open(args.maf, newline="\n") as fin:
        header = fin.readline().rstrip("\n").split("\t")
        col = {}
        for i, name in enumerate(header):
            col.setdefault(name, i)
        for need in ("Chromosome", "Start_Position", "End_Position"):
            if need not in col:
                sys.exit(f"{args.maf}: no {need} column")
        spans = []
        for line in fin:
            f = line.rstrip("\n").split("\t")
            start, end = int(f[col["Start_Position"]]), int(f[col["End_Position"]])
            spans.append((f[col["Chromosome"]], min(start, end), max(start, end)))

    # One sweep per chromosome: queries sorted by start; intervals (sorted by start in the BED)
    # enter the active heap once they start at or before the query's end, and leave it once they
    # end before the current query's start, which no later query can then reach either.
    by_chrom = {}
    for k, (chrom, start, end) in enumerate(spans):
        by_chrom.setdefault(chrom, []).append((start, end, k))
    for queries in by_chrom.values():
        queries.sort()
    found = [set() for _ in spans]

    def sweep(queries, ivs):
        active, pending = [], None
        ivs = iter(ivs)
        for qs, qe, k in queries:
            while True:
                if pending is None:
                    pending = next(ivs, False)
                if not pending or pending[0] + 1 > qe:   # BED start is 0-based
                    break
                heapq.heappush(active, (pending[1], pending[0], pending[2]))
                pending = None
            while active and active[0][0] < qs:
                heapq.heappop(active)
            for end, start, cls in active:
                if start + 1 <= qe and end >= qs:
                    found[k].add(cls)

    current, block = None, []
    for chrom, start, end, cls in intervals(args.bed, by_chrom):
        if chrom != current:
            if current is not None:
                sweep(by_chrom[current], block)
            current, block = chrom, []
        block.append((start, end, cls))
    if current is not None:
        sweep(by_chrom[current], block)

    n_hit = 0
    with open(args.maf, newline="\n") as fin, open(args.output, "w", newline="\n") as fout:
        fin.readline()
        fout.write("\t".join(header + COLUMNS) + "\n")
        for line, classes in zip(fin, found):
            value = ";".join(c for c in ORDER if c in classes) or MISSING
            n_hit += value != MISSING
            fout.write(line.rstrip("\n") + "\t" + value + "\n")
    print(f"{args.output}: {n_hit} of {len(spans)} variants in a repeat region", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("rmsk")
    b.add_argument("trf")
    b.add_argument("output")
    a = sub.add_parser("annotate")
    a.add_argument("--maf", required=True)
    a.add_argument("--bed", required=True)
    a.add_argument("--output", required=True)
    args = ap.parse_args()
    build(args) if args.cmd == "build" else annotate(args)


if __name__ == "__main__":
    main()
