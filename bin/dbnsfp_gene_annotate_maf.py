#!/usr/bin/env python3
"""
MuSA — dbnsfp_gene_annotate_maf.py

Extend dbNSFP's GENE-level annotation to every variant of a gene, keyed by Hugo_Symbol.

Why: the per-variant dbNSFP step (dbnsfp_annotate_vcf_chr) matches on the amino-acid change, so it
only attaches dbNSFP's gene columns to dbNSFP-matched (essentially missense/coding) rows. Every other
variant of the same gene — intronic, UTR, splice, synonymous, non-coding — is left with empty gene
columns, even though the information is purely gene-level and perfectly well known. Measured on a real
MAF: Gene_full_name is 74% filled on coding rows but only 10% on non-coding ones; GO_biological_process
10%, Pathway(KEGG)_full 4%, HPO_id 7%, gnomAD_LOEUF 10%.

This step joins the dbNSFP *gene* file (dbNSFP5.x_gene.gz — one row per gene, keyed by Gene_name) on
Hugo_Symbol and fills those columns for ALL rows.

Managed columns are computed at runtime as the intersection of the MAF header with the gene-file
header. Every gene-file column is gene-level by construction, so the intersection is exactly the
gene-level annotation set (~143 of the file's 150 columns: Gene_full_name, OMIM_id, Entrez_gene_id,
Refseq_id, ucsc_id, Function_description, Disease_description, MIM_phenotype_id, MIM_disease,
Orphanet_*, GenCC_*, HPO_id/name, GO_*, Pathway(*), Tissue_specificity, HPA_consensus_*, Essential_gene*,
GDI*, RVIS*, LoFtool, Gene damage prediction (*), ExAC/gnomAD constraint, MGI_*, ZFIN_*, ...).

Intersecting (rather than hardcoding) also means the 7 gene-file columns that CLEAN_COLUMNS
deliberately drops as duplicates — Gene_name→Hugo_Symbol, Ensembl_gene→Gene, chr→Chromosome,
MIM_id→OMIM_id, Uniprot_acc→SWISSPROT, Uniprot_id→Uniprot_entry, CCDS_id→CCDS — are never
re-introduced, and no new column is ever appended (the MAF keeps its exact width).

Coding rows already carry these values from the same dbNSFP release, so overwriting them is
idempotent; the win is the non-coding rows. Genes absent from the gene file are left untouched (never
wipe a good value to NA).

Run AFTER clean_columns (final column names) and BEFORE clingen_annotate_maf, whose ClinGen dosage
values are authoritative and must win over the gene file's older ClinGen_Haploinsufficiency_* copies.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import sys

# The gene file's own identity/alias columns: used for lookup, never written into the MAF.
GENE_KEY = "Gene_name"
ALIAS_COLS = ("Gene_old_names", "Gene_other_names")


def _open_text(path: str):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(
        path, encoding="utf-8", errors="replace"
    )


def load_gene_table(gene_file: str, managed: list[str]) -> tuple[dict, dict]:
    """(primary, alias) lookups: GENE_UPPER -> tuple of values ordered like `managed`.

    `alias` maps old/other gene symbols onto the same tuple, so a MAF using a legacy symbol still
    resolves. Primary names always win over aliases.
    """
    primary: dict[str, tuple] = {}
    alias: dict[str, tuple] = {}
    with _open_text(gene_file) as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        idx = {c: i for i, c in enumerate(header)}
        if GENE_KEY not in idx:
            sys.exit(f"ERROR: '{GENE_KEY}' not in gene-file header {gene_file}")
        m_idx = [idx[c] for c in managed]
        k_idx = idx[GENE_KEY]
        a_idx = [idx[c] for c in ALIAS_COLS if c in idx]

        for row in reader:
            if len(row) <= k_idx:
                continue
            name = row[k_idx].strip().upper()
            if not name or name == ".":
                continue
            values = tuple(row[i] if i < len(row) else "." for i in m_idx)
            primary[name] = values
            for ai in a_idx:
                if ai >= len(row):
                    continue
                for a in row[ai].replace("|", ";").split(";"):
                    a = a.strip().upper()
                    if a and a != "." and a not in alias:
                        alias[a] = values
    return primary, alias


def annotate(maf_in: str, maf_out: str, gene_file: str, gene_col: str) -> tuple[int, int, int]:
    with _open_text(gene_file) as fh:
        gene_header = next(csv.reader(fh, delimiter="\t"))
    gene_cols = set(gene_header)

    with open(maf_in, encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        if gene_col not in header:
            sys.exit(f"ERROR: gene column '{gene_col}' not in MAF header")
        g_idx = header.index(gene_col)

        # Fill only columns the MAF already has: no widening, no re-introducing deduped names.
        managed = [c for c in header if c in gene_cols and c != GENE_KEY]
        if not managed:
            sys.exit("ERROR: no gene-level columns shared between MAF and gene file")
        m_idx = [header.index(c) for c in managed]

        primary, alias = load_gene_table(gene_file, managed)
        print(
            f"gene table: {len(primary)} genes (+{len(alias)} aliases); "
            f"managed columns: {len(managed)}/{len(gene_cols)}",
            file=sys.stderr,
        )

        n = hit = 0
        with open(maf_out, "w", encoding="utf-8", newline="") as out:
            writer = csv.writer(out, delimiter="\t", lineterminator="\n")
            writer.writerow(header)
            for row in reader:
                if len(row) < len(header):
                    row = row + [""] * (len(header) - len(row))
                gene = row[g_idx].strip().upper()
                values = primary.get(gene) or alias.get(gene)
                if values is not None:
                    for pos, val in zip(m_idx, values, strict=False):
                        row[pos] = val
                    hit += 1
                n += 1
                writer.writerow(row)
    return n, hit, len(managed)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extend dbNSFP gene-level annotation to every variant of a gene.")
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--gene-file", required=True, help="dbNSFP5.x_gene.gz")
    ap.add_argument("--gene-col", default="Hugo_Symbol")
    args = ap.parse_args()

    n, hit, ncols = annotate(args.input, args.output, args.gene_file, args.gene_col)
    pct = (100.0 * hit / n) if n else 0.0
    print(f"rows: {n}; gene matched: {hit} ({pct:.1f}%); columns filled: {ncols}", file=sys.stderr)


if __name__ == "__main__":
    main()
