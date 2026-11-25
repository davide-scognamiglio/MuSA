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
  - Every variant that survived preprocessing, annotated and merged into one table, one row per
    variant. Basic mode (VEP with ClinVar and ClinGen, vcf2maf, ClinGen gene curations, HPO match
    and onset, ClinVar PS1/PM5 evidence and submission comments, PubTator3 literature links, the
    sample's own genotype, transcript lengths, repeat regions): 195 columns. Extended mode adds
    dbNSFP's variant and gene columns, the VEP plugins, gnomAD v4.1 exomes counts and RENOVO's
    `RENOVO_Class` / `PL_score`: 962 columns as of this version.
    This number changes as annotation sources change: treat it as approximate rather than a
    stable interface.
- `<patient>.filtered.maf`
  - The same table after the three-tier filter: gene panel (`--panel`), HPO phenotype panel
    (from the samplesheet's `hpo` column, see the `HPO_*` columns in [usage](usage.md#filtering)), and allele frequency (`--max_freq`), plus
    `--drop_benign` if set. This is the file to hand to a reviewer.
- `<patient>.transcripts.tsv.gz`
  - Every transcript VEP reports for each variant, one line per variant and transcript, keyed like
    the MAF (`Chromosome`, `Start_Position`, `Reference_Allele`, `Tumor_Seq_Allele2`) and ordered
    MANE Select, MANE Plus Clinical, the MAF's transcript, Ensembl canonical, then by impact.
    `MuSA_pick` is `yes` on the transcript the MAF row reports. Columns: `Feature`, `SYMBOL`,
    `Gene`, `BIOTYPE`, `Consequence`, `IMPACT`, `HGVSc`, `HGVSp`, `EXON`, `INTRON`,
    `cDNA_position`, `CDS_position`, `Protein_position`, `Amino_acids`, `Codons`, `STRAND`,
    `FLAGS`, `CANONICAL`, `MANE_SELECT`, `MANE_PLUS_CLINICAL`, `TSL`, `APPRIS`, `CCDS`, `ENSP`,
    `SWISSPROT`, `SIFT`, `PolyPhen` (multi-value fields `,`-separated), and as the last columns
    `cDNA_length`, `CDS_length`, `Protein_length` (the transcript's lengths). In extended mode these are
    followed by each transcript's own dbNSFP scores and predictions, every transcript-aligned
    `*_score` and `*_pred` column (41 with dbNSFP 5.3: `SIFT_score`, `REVEL_score`,
    `AlphaMissense_score`, ...), named as in the MAF and written as dbNSFP writes them; `.` where
    dbNSFP has no record for the transcript (it covers non-synonymous changes only). In the MAF
    the same columns hold one value, for the MANE transcript (see `--dbnsfp_transcript_scores` in
    [usage](usage.md)). An intergenic variant has no line. About 0.6 MB per 1,000 variants.
- `<patient>_maf_dashboard.html`
  - Self-contained interactive report: a summary panel plus a sortable, searchable table of the
    filtered variants, showing gene, HGVS nomenclature, consequence, ClinVar significance and
    review status, gnomAD population-maximum frequency, and RENOVO score (extended mode). Its **Annotation
    sources** view lists every source the run annotated from, with the installed version (see
    [`sources.md`](sources.md) for the columns each one fills).

</details>

### About the MAF format

MuSA consolidates its output as MAF rather than VCF deliberately. MAF enforces one row per variant
against a single selected transcript, so the transcript multiplicity that makes VEP's VCF output
awkward to review is resolved before the file is written. Its flat, column-based schema also takes
hundreds of heterogeneous annotations without nesting, and carries a sample identifier per row, so
per-patient MAFs can be concatenated into a cohort table and read directly by tools such as
[maftools](https://bioconductor.org/packages/maftools/).

The transcript is VEP's `--pick` choice (every other transcript is in `<patient>.transcripts.tsv.gz`
and in the report's transcript selector), ordered by consequence severity first (`--pick_order
rank,mane_select,...`): a variant is reported with its most severe consequence on any transcript,
which is not always the MANE Select one. On the ClinGen Evidence Repository, 342 of the 11,714
variants that overlap a MANE transcript (2.9%) are reported on another transcript, for example a
`stop_gained` on an NMD transcript that is missense on MANE. `MANE_SELECT` is empty on those rows.
dbNSFP lists only non-synonymous changes, so a variant reported as missense on another transcript
but synonymous or intronic on MANE can have no dbNSFP values at all.

`--vep_pick_order` sets this order. Starting it with `mane_select` (for example
`mane_select,mane_plus_clinical,rank,canonical,appris,tsl,biotype,ccds,length`) reports a variant
on a MANE Select transcript whenever VEP gives it any consequence on one, and the rest by severity.
"Any consequence" includes upstream, downstream and intronic ones, in any gene: when a variant's
damaging effect is on a transcript that is not MANE and it lies near another gene's MANE
transcript, the row moves to that other gene. On NA12878 chr22 (543 variants) a MANE-first order
moved 98 rows to another transcript, 4 of them to another gene, each hiding a HIGH or MODERATE
consequence (a TUBA8 `stop_gained` reported as USP18 `upstream_gene_variant`). Check
`Hugo_Symbol` and the transcripts table before reading such a row as benign.

Both MAFs are tab-separated with a single header line. Missing values are written as `.`: the
pipeline normalises `NA`, empty cells and `.` to that one spelling, so a missing value tests the
same way in every column.

#### When "missing" carries meaning

A few columns distinguish *looked up and absent* from *not looked up*, because the difference
changes what the row says:

| Value | Columns | Meaning |
|---|---|---|
| `.` | all | no value: not annotated, or the source has nothing for the variant |
| `not_found` | `gnomADe41_status` | the variant's chromosome was queried in gnomAD v4.1 exomes and gnomAD has no record of the variant |
| `found` | `gnomADe41_status` | gnomAD v4.1 exomes has the variant (the `gnomADe41_*` counts are filled) |
| `not_requested` | `HPO_match`, `HPO_match_score`, `HPO_matched_terms`, `HPO_best_disease`, `HPO_panel` | the samplesheet gave no HPO terms, so no comparison was made (`none` means compared, nothing matched) |
| `unannotated` | `HPO_match`, `HPO_onset` | HPO has no phenotype (or disease) annotation for the gene |
| `0` | `ClinVar_SCV_*_n` | the variant is in ClinVar and no counted submission says that; `.` means no ClinVar record |
| `.` | `Repeat_region` | the variant overlaps none of the repeat intervals (RepeatMasker simple, low-complexity, satellite; Tandem Repeats Finder) |
| `.` | `Zygosity` | the sample has no genotype call at the site (the other `Sample_*` columns are `.` too) |

#### Columns holding several values

| Columns | Separator | Example |
|---|---|---|
| `HPO_onset` | `;` between diseases, `,` between one disease's onsets | `OMIM:615681=Juvenile onset (HP:0003621),Childhood onset (HP:0011463)` |
| `ClinVar_SCV_PS3_codes`, `ClinVar_SCV_BS3_codes` | `;` between codes, `:` before the count | `PS3:4;PS3_Moderate:1` |
| `ClinVar_EP_codes` | `; ` between expert-panel submissions, `,` between codes | `Pathogenic: PS3,PM2_Supporting [ClinGen ... VCEP]` |
| `PubTator3_pmids`, `PubTator3_source`, `ClinVar_SCV_func_pmids`, `PUBMED`, `Existing_variation`, `MaveDB_score` (VEP plugin) | `,` | `41892021,40730740` |
| `Consequence` and other VEP multi-value fields | `,` (VEP's `&`) | `missense_variant,splice_region_variant` |
| `HPO_matched_terms`, `ClinVar_PM5` | `; ` | `R978H 3★; R978S 1★` |
| `Comphet_trans`, `Comphet_cis_or_unknown` | `;` | `TTN:p.Arg100Cys;TTN:p.Gly2Ser` |
| `Cohort_carriers` | `,` | `HG00097,HG00157` |
| `Repeat_region` | `;`, in the order `Simple_repeat`, `Low_complexity`, `Satellite`, `TRF` | `Simple_repeat;TRF` |
| `Sample_AD` | `,`, reference first | `12,9` |


### Family and cohort columns

Written in [family and cohort modes](usage.md#family-and-cohort-modes) only.

| Column | Values | Meaning |
|---|---|---|
| `GT_`, `DP_`, `GQ_`, `AD_`, `VAF_<sample>` | as in `Sample_*` | each member's call, members in samplesheet order (proband first); in `<group>.genotypes.tsv.gz` instead above `--max_member_columns` members |
| `Inheritance` | `de_novo`, `maternal`, `paternal`, `biparental`, `not_in_proband`, `unknown` | where the proband's alternate allele comes from, from the parents' genotypes; `biparental`: a homozygous proband, one allele from each parent |
| `Inheritance_check` | `pass`; `unchecked`; `parent_missing`, `parent_no_call`, `parent_low_depth`, `parent_low_gq`, `parent_alt_reads`; `proband_no_call`, `proband_low_gq`, `proband_allele_balance`; `both_parents_carry`; `mendelian_error` | why `Inheritance` is what it is: `unchecked` is a de novo call from a VCF without DP, GQ or AD; `both_parents_carry` is a heterozygous proband whose parents both carry the variant, so either could have passed it on |
| `Segregation_affected`, `Segregation_unaffected` | `k/n` | members carrying the variant / members with a call, among the affected and the unaffected |
| `Comphet_trans` | `GENE:p.change;...` | the proband's other heterozygous variants in the same gene that come from the other parent (in trans) |
| `Comphet_cis_or_unknown` | `GENE:p.change;...` | its other heterozygous variants in the gene whose phase the parents do not establish |
| `Cohort_called_n`, `Cohort_carriers_n`, `Cohort_het_n`, `Cohort_hom_n` | counts | members with a call, carrying it, heterozygous (hemizygous included), homozygous |
| `Cohort_AF` | 0 to 1 | alternate allele frequency among the called members |
| `Cohort_carrier_families_n` | count | carriers counted once per samplesheet `family` |
| `Cohort_affected_carriers_n`, `Cohort_unaffected_carriers_n` | counts | carriers by affected status |
| `Cohort_carriers` | names | carrier samples, up to 50 |
| `Family_members` | `sample:role:sex:affected;...` | family mode: every member in samplesheet order (proband first), affected `yes` / `no` / `unknown`; the same on every row |

`Zygosity` and `Sample_*` describe the proband in family mode and are `.` in cohort mode. Group
outputs, next to the MAFs: `<group>.genotypes.tsv.gz` (more members than `--max_member_columns`) and,
for a cohort, `<group>.genes.tsv`.

## Setup workflow

Reference data is written under `--data_dir` in the layout the annotate workflow expects
(`vep_data/`, `clingen/`, `hpo/`, reference genome; `dbNSFP/` and the VEP plugin data in extended mode). Alongside it:

<details markdown="1">
<summary>Output files</summary>

- `setup_report.html`
  - Integrity report listing every downloaded resource with its version, source URL, and SHA-256
    checksum, each marked `VERIFIED`, `MISMATCH` or `PENDING`.
- `*_manifest.yaml`
  - The merged manifest: a machine-readable record of exactly which database versions were
    installed and what their checksums were. Keep it: it is the audit trail for any annotation
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
