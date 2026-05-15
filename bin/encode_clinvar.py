#!/usr/bin/env python3
"""
encode_clinvar.py

Encodes ClinVar significance and review status columns into single,
canonical ACMG classification values.

Usage:
    python3 encode_clinvar.py \\
        --file        <path_to_tsv> \\
        --sig_col     <clinvar_significance_column_name> \\
        --rev_col     <clinvar_review_column_name> \\
        --output      <output_file_path>   # optional; default: encoded_<input>
"""

import argparse
import sys
import os
import pandas as pd


# ----------------------------- ENCODING LOGIC --------------------------------

def classify_assertion(assertion: str) -> str:
    """
    Classify a single assertion term (one comma-joined slice of a ClinVar record).
    Returns one of: P, LP, B, LB, VUS, NC, MOD
    """
    if not assertion or pd.isna(assertion):
        return "NA"

    terms = [t.strip() for t in assertion.split(",")]

    if any("Pathogenic" in t for t in terms):
        return "P"
    if any("Likely_pathogenic" in t for t in terms):
        return "LP"
    if any("Benign" in t for t in terms):
        return "B"
    if any("Likely_benign" in t for t in terms):
        return "LB"
    if any("Uncertain_significance" in t for t in terms):
        return "VUS"
    if any("Conflicting_classifications" in t for t in terms):
        return "VUS"
    if any(
        t in ("", "other",
              "no_classifications_from_unflagged_records",
              "no_classification_for_the_single_variant",
              "not_provided")
        for t in terms
    ):
        return "NC"

    return "MOD"


def encode_clinvar_sig(value: str) -> str:
    """
    Collapse all assertions in a ClinVar significance string (slash-separated)
    into a single ACMG class label.

    Returns one of:
        Pathogenic | Likely Pathogenic | VUS | Likely benign | Benign | Not classified
    """
    if not value or pd.isna(value):
        return "Not classified"

    assertions = [a.strip() for a in str(value).split("/")]
    calls = [classify_assertion(a) for a in assertions]
    calls = [c for c in calls if c not in ("MOD", "NA")]

    if not calls:
        return "VUS"

    pathogenic_side = {"P", "LP"}
    benign_side     = {"B", "LB"}
    calls_set       = set(calls)

    # Conflict between pathogenic and benign → VUS
    if calls_set & pathogenic_side and calls_set & benign_side:
        return "VUS"

    # All pathogenic-side
    if calls_set <= pathogenic_side:
        return "Pathogenic" if "P" in calls_set else "Likely Pathogenic"

    # All benign-side
    if calls_set <= benign_side:
        return "Benign" if "B" in calls_set else "Likely benign"

    # No actionable classification
    if calls_set <= {"NC"}:
        return "Not classified"

    return "VUS"


_REVIEW_MAP = {
    "practice_guideline":                                       "4",
    "reviewed_by_expert_panel":                                 "3",
    "criteria_provided,_multiple_submitters,_no_conflicts":     "2",
    "criteria_provided,_conflicting_classifications":           "1",
    "criteria_provided,_single_submitter":                      "1",
    "no_assertion_criteria_provided":                           "0",
    "no_classification_provided":                               "0",
    "no_classification_for_the_single_variant":                 "0",
    "no_classifications_from_unflagged_records":                "0",
}

def encode_clinvar_rev(value: str) -> str | None:
    """
    Convert a ClinVar review-status string to a numeric star rating (0–4).
    Returns None for missing values, and warns on unrecognised strings.
    """
    if not value or pd.isna(value):
        return None

    key = str(value).lower().strip()
    result = _REVIEW_MAP.get(key)

    if result is None:
        print(f"[WARNING] Unrecognised review status: '{value}'", file=sys.stderr)

    return result


# ----------------------------- MAIN ------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Encode ClinVar significance and review status into canonical ACMG labels."
    )
    parser.add_argument(
        "-f", "--file",
        required=True,
        help="Input file (TSV / MAF). Required."
    )
    parser.add_argument(
        "-s", "--sig_col",
        default="clinvar_clnsig",
        help="Column name for ClinVar significance (default: clinvar_clnsig)"
    )
    parser.add_argument(
        "-r", "--rev_col",
        default="clinvar_review",
        help="Column name for ClinVar review status (default: clinvar_review)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output file path (default: encoded_<input_basename>)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.isfile(args.file):
        sys.exit(f"[ERROR] Input file not found: {args.file}")

    output_path = args.output or os.path.join(
        os.path.dirname(args.file),
        "encoded_" + os.path.basename(args.file)
    )

    print(f"[INFO] Reading input: {args.file}", file=sys.stderr)
    df = pd.read_csv(args.file, sep="\t", dtype=str, low_memory=False)

    for col in (args.sig_col, args.rev_col):
        if col not in df.columns:
            sys.exit(
                f"[ERROR] Column '{col}' not found in input file.\n"
                f"Available columns: {', '.join(df.columns)}"
            )

    sig_out = f"encoded_{args.sig_col}"
    rev_out = f"encoded_{args.rev_col}"

    print(f"[INFO] Encoding '{args.sig_col}' → '{sig_out}'", file=sys.stderr)
    print(f"[INFO] Encoding '{args.rev_col}' → '{rev_out}'",  file=sys.stderr)

    df[sig_out] = df[args.sig_col].apply(encode_clinvar_sig)
    df[rev_out] = df[args.rev_col].apply(encode_clinvar_rev)

    print(f"[INFO] Writing output: {output_path}", file=sys.stderr)
    df.to_csv(output_path, sep="\t", index=False)
    print("[INFO] Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
