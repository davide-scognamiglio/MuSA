#!/usr/bin/env python3
"""
renovo_adj_acmg.py

Applies the Renovo adjusted ACMG score to missense variants.

For Missense_Mutation variants with a valid acmg_score in [0, 5] and a valid
PL_score, the score is pushed above 5 (toward pathogenic) or below 0 (toward
benign) based on the PL_score:

    PL_score > 0.5  →  renovo_adj_acmg_score = 5  + (PL_score - 0.5) * 10
    PL_score <= 0.5 →  renovo_adj_acmg_score = 0  - (0.5 - PL_score) * 10

All other variants keep their original acmg_score unchanged.
The result is written to a new column: renovo_adj_acmg_score.

Usage:
    python3 renovo_adj_acmg.py \\
        --file            <path_to_tsv>              (required)
        --variant_col     <variant_class_column>     [default: Variant_Classification]
        --acmg_col        <acmg_score_column>        [default: acmg_score]
        --pl_col          <pl_score_column>          [default: PL_score]
        --output          <output_file_path>         [default: renovo_adj_<input>]
"""

import argparse
import os
import sys

import pandas as pd
import numpy as np


# ----------------------------- ADJUSTMENT LOGIC ------------------------------

def renovo_adj_acmg_score(
    variant_class: pd.Series,
    acmg_score: pd.Series,
    pl_score: pd.Series,
) -> pd.Series:
    """
    Vectorised Renovo ACMG score adjustment.

    Conditions for adjustment (all must be true):
      - Variant_Classification == "Missense_Mutation"
      - acmg_score is not NaN
      - 0 <= acmg_score <= 5
      - PL_score is not NaN

    Adjusted value:
      PL_score > 0.5  →  5  + (PL_score - 0.5) * 10   (push toward pathogenic)
      PL_score <= 0.5 →  0  - (0.5 - PL_score) * 10   (push toward benign)
    """
    acmg  = pd.to_numeric(acmg_score, errors="coerce")
    pl    = pd.to_numeric(pl_score,   errors="coerce")

    eligible = (
        (variant_class == "Missense_Mutation") &
        acmg.notna() &
        (acmg >= 0) &
        (acmg <= 5) &
        pl.notna()
    )

    adjusted = np.where(
        pl > 0.5,
        5  + (pl - 0.5) * 10,   # push above 5
        0  - (0.5 - pl) * 10    # push below 0
    )

    return pd.Series(
        np.where(eligible, adjusted, acmg),
        index=acmg_score.index,
        name="renovo_adj_acmg_score",
        dtype=float,
    )


# ----------------------------- MAIN ------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply Renovo adjusted ACMG score to missense variants."
    )
    parser.add_argument(
        "-f", "--file",
        required=True,
        help="Input file (TSV / MAF). Required."
    )
    parser.add_argument(
        "--variant_col",
        default="Variant_Classification",
        help="Column with variant classification (default: Variant_Classification)"
    )
    parser.add_argument(
        "--acmg_col",
        default="acmg_score",
        help="Column with ACMG score (default: acmg_score)"
    )
    parser.add_argument(
        "--pl_col",
        default="PL_score",
        help="Column with Renovo PL score (default: PL_score)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (default: renovo_adj_<input_basename>)"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not os.path.isfile(args.file):
        sys.exit(f"[ERROR] Input file not found: {args.file}")

    output_path = args.output or os.path.join(
        os.path.dirname(args.file) or ".",
        "renovo_adj_" + os.path.basename(args.file)
    )

    print(f"[INFO] Reading input: {args.file}", file=sys.stderr)
    df = pd.read_csv(args.file, sep="\t", dtype=str, low_memory=False)

    for col in (args.variant_col, args.acmg_col, args.pl_col):
        if col not in df.columns:
            sys.exit(
                f"[ERROR] Column '{col}' not found in input file.\n"
                f"Available columns: {', '.join(df.columns)}"
            )

    print(
        f"[INFO] Adjusting '{args.acmg_col}' using '{args.pl_col}' "
        f"for '{args.variant_col}' == 'Missense_Mutation' → 'renovo_adj_acmg_score'",
        file=sys.stderr,
    )

    df["renovo_adj_acmg_score"] = renovo_adj_acmg_score(
        variant_class=df[args.variant_col],
        acmg_score=df[args.acmg_col],
        pl_score=df[args.pl_col],
    )

    # Report how many rows were actually adjusted
    acmg_numeric = pd.to_numeric(df[args.acmg_col], errors="coerce")
    n_adjusted = (
        (df[args.variant_col] == "Missense_Mutation") &
        acmg_numeric.notna() &
        (acmg_numeric >= 0) & (acmg_numeric <= 5) &
        pd.to_numeric(df[args.pl_col], errors="coerce").notna()
    ).sum()
    print(f"[INFO] Variants adjusted: {n_adjusted} / {len(df)}", file=sys.stderr)

    print(f"[INFO] Writing output: {output_path}", file=sys.stderr)
    df.to_csv(output_path, sep="\t", index=False)
    print("[INFO] Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
