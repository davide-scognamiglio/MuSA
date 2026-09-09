# MuSA: Output

## Introduction

This document describes the output produced by the pipeline.

MuSA has two workflows, and they write to different places:

- `--workflow annotate` writes per-patient results under `--outdir`.
- `--workflow setup` writes reference data and an integrity report under `--data_dir`.

## Annotate workflow

Results are written to `<outdir>/<date>/<patient>/`, where `<date>` is the run date in `yyMMdd`
form. One directory per patient in the samplesheet:

```
results/
└── 260907/
    ├── 5510/
    │   ├── 5510.raw.maf
    │   ├── 5510.filtered.maf
    │   └── 5510_maf_dashboard.html
    └── 5724/
        └── ...
```

<details markdown="1">
<summary>Output files</summary>

- `<patient>.raw.maf`
  - Every variant that survived preprocessing, annotated by all four branches and merged into one
    table. Up to ~937 columns per variant in extended mode, one row per variant.
- `<patient>.filtered.maf`
  - The same table after the three-tier filter: gene panel (`--panel`), HPO-matched gene panel
    (from the samplesheet's `hpo` column), and allele frequency (`--max_freq`), plus
    `--drop_benign` if set. This is the file to hand to a reviewer.
- `<patient>_maf_dashboard.html`
  - Self-contained interactive report: a summary panel plus a sortable, searchable table of the
    filtered variants, showing gene, HGVS nomenclature, consequence, ClinVar significance and
    review status, gnomAD population-maximum frequency, and RENOVO score.

</details>

### About the MAF format

MuSA consolidates its output as MAF rather than VCF deliberately. MAF enforces one row per variant
against a single selected transcript, so the transcript multiplicity that makes VEP's VCF output
awkward to review is resolved before the file is written. Its flat, column-based schema also takes
hundreds of heterogeneous annotations without nesting, and carries a sample identifier per row, so
per-patient MAFs can be concatenated into a cohort table and read directly by tools such as
[maftools](https://bioconductor.org/packages/maftools/).

Both MAFs are tab-separated with a single header line. Missing values are written as `.` — the
pipeline normalises `NA`, empty cells and `.` to that one spelling, so a missing value tests the
same way in every column.

## Setup workflow

Reference data is written under `--data_dir` in the layout the annotate workflow expects
(`vep_data/`, `dbNSFP/`, ANNOVAR databases, reference genome). Alongside it:

<details markdown="1">
<summary>Output files</summary>

- `setup_report.html`
  - Integrity report listing every downloaded resource with its version, source URL, and SHA-256
    checksum, each marked `VERIFIED`, `MISMATCH` or `PENDING`.
- `*_manifest.yaml`
  - The merged manifest: a machine-readable record of exactly which database versions were
    installed and what their checksums were. Keep it — it is the audit trail for any annotation
    produced against this data directory.

</details>

## Pipeline information

<details markdown="1">
<summary>Output files</summary>

- `<outdir>/pipeline_info/`
  - Nextflow execution reports: `execution_report_*.html`, `execution_timeline_*.html`,
    `execution_trace_*.txt`, and `pipeline_dag_*.html`. The trace file carries per-task runtime and
    peak memory, which is what to read when tuning process resources.

</details>
