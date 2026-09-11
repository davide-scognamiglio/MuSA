#!/usr/bin/env python3
import pysam
import argparse
import csv
import os
import sys


def get_bases(fasta_handle, chrom, pos, window=10):
    """Return reference sequence around a position from an already-open FastaFile."""
    if not chrom.startswith("chr"):
        chrom = "chr" + chrom
    start = max(0, pos - window - 1)  # pysam uses 0-based
    end = pos + window
    seq = fasta_handle.fetch(chrom, start, end)
    return seq.upper()


def add_ref_context(input_file, output_file, fasta, window=10, chrom_col=None, pos_col=None):
    """Add a column with reference context for each variant.

    Streams the input row by row rather than reading it into memory: MuSA runs this on the
    vcf2maf output before the dbNSFP/VEP merge, and a WGS-scale callset is millions of rows.
    A `list(reader)` here held the entire table in memory as Python dicts alongside the output
    being written, which is what actually OOM-killed this step -- the row width (~117 columns
    pre-merge) was never the problem, the row count was. The FASTA file is also opened once and
    reused, rather than reopened per row: pysam.FastaFile() re-reads its .fai index on every open,
    which is wasted I/O at any scale and becomes a lot of wasted I/O at millions of rows.
    """
    ext = os.path.splitext(input_file)[1].lower()

    # Set default columns based on file type
    if ext == ".maf":
        chrom_col = chrom_col or "Chromosome"
        pos_col = pos_col or "Start_Position"
    elif ext in (".vcf", ".txt"):
        chrom_col = chrom_col or "chrom"
        pos_col = pos_col or "pos"
    else:
        raise ValueError("Input must be a VCF, MAF, or tab-delimited TXT file.")

    with open(input_file, newline="") as in_f, \
         open(output_file, "w", newline="") as out_f, \
         pysam.FastaFile(fasta) as fasta_handle:

        if ext == ".vcf":
            # Skip meta-info lines, then read the #CHROM header line, without ever holding the
            # rest of the file as a list.
            header = None
            for line in in_f:
                if line.startswith("##"):
                    continue
                header = line.lstrip("#").strip().split("\t")
                break
            if header is None:
                raise ValueError("No header line found in VCF.")
            reader = (dict(zip(header, line.strip().split("\t"))) for line in in_f)
        else:
            reader = csv.DictReader(in_f, delimiter="\t")
            header = reader.fieldnames

        if chrom_col not in header or pos_col not in header:
            raise ValueError(f"Columns {chrom_col} and {pos_col} must be present in the file.")

        out_header = header + ["ref_context"]
        writer = csv.DictWriter(out_f, fieldnames=out_header, delimiter="\t")
        writer.writeheader()

        for row_dict in reader:
            chrom = row_dict.get(chrom_col)
            pos = row_dict.get(pos_col)
            try:
                context = get_bases(fasta_handle, chrom, int(pos), window)
            except Exception as e:
                context = "NA"
                print(f"Warning: Could not get context for {chrom}:{pos} - {e}", file=sys.stderr)
            row_dict["ref_context"] = context
            writer.writerow(row_dict)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add reference context column to a variant file")
    parser.add_argument("--input", required=True, help="Input VCF, MAF, or TXT file")
    parser.add_argument("--output", required=True, help="Output file with ref_context column")
    parser.add_argument("--fasta", required=True, help="Reference FASTA with .fai index")
    parser.add_argument("--window", type=int, default=10, help="Number of bases around variant")
    parser.add_argument("--chrom_col", default=None, help="Chromosome column name (override defaults)")
    parser.add_argument("--pos_col", default=None, help="Position column name (override defaults)")

    args = parser.parse_args()

    add_ref_context(args.input, args.output, args.fasta, args.window, args.chrom_col, args.pos_col)
