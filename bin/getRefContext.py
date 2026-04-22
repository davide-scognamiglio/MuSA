#!/usr/bin/env python3
import pysam
import argparse
import csv
import os
import sys

def get_bases(fasta, chrom, pos, window=10):
    """Return reference sequence around a position."""
    if not chrom.startswith("chr"):
        chrom = "chr" + chrom
    with pysam.FastaFile(fasta) as f:
        start = max(0, pos - window - 1)  # pysam uses 0-based
        end = pos + window
        seq = f.fetch(chrom, start, end)
    return seq.upper()


def add_ref_context(input_file, output_file, fasta, window=10, chrom_col=None, pos_col=None):
    """Add a column with reference context for each variant."""
    ext = os.path.splitext(input_file)[1].lower()
    
    # Set default columns based on file type
    if ext == ".maf":
        chrom_col = chrom_col or "Chromosome"
        pos_col = pos_col or "Start_Position"
    elif ext == ".vcf":
        chrom_col = chrom_col or "chrom"
        pos_col = pos_col or "pos"
    elif ext == ".txt":
        chrom_col = chrom_col or "chrom"
        pos_col = pos_col or "pos"
    else:
        raise ValueError("Input must be a VCF, MAF, or tab-delimited TXT file.")
    
    # Read input
    if ext == ".vcf":
        with open(input_file) as f:
            lines = [l for l in f if not l.startswith("##")]
        header = lines[0].lstrip("#").strip().split("\t")
        data_lines = lines[1:]
    else:
        with open(input_file) as f:
            reader = csv.DictReader(f, delimiter="\t")
            header = reader.fieldnames
            data_lines = list(reader)
    
    # Check required columns
    if chrom_col not in header or pos_col not in header:
        raise ValueError(f"Columns {chrom_col} and {pos_col} must be present in the file.")
    
    out_header = header + ["ref_context"]
    
    with open(output_file, "w", newline="") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=out_header, delimiter="\t")
        writer.writeheader()
        
        for row in data_lines:
            if isinstance(row, str):
                # VCF case: split line into dict
                values = row.strip().split("\t")
                row_dict = dict(zip(header, values))
            else:
                row_dict = row
            try:
                chrom = row_dict[chrom_col]
                pos = int(row_dict[pos_col])
                context = get_bases(fasta, chrom, pos, window)
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
