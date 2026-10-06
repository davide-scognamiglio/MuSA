<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/images/MuSA_logo_dark.png">
    <img alt="MuSA" src="docs/images/MuSA_logo_light.png">
  </picture>
</h1>

[![Nextflow](https://img.shields.io/badge/version-%E2%89%A525.10.0-green?style=flat&logo=nextflow&logoColor=white&color=%230DC09D&link=https%3A%2F%2Fnextflow.io)](https://www.nextflow.io/)
[![run with docker or singularity](https://img.shields.io/badge/run%20with-docker%20%7C%20singularity-1d355c?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)
[![License: CC BY-NC 4.0](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)](LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.1186%2Fs12859--026--06513--0-blue)](https://doi.org/10.1186/s12859-026-06513-0)

**MuSA (Multi-Source variant Annotation)** turns a germline VCF into an interpretation-ready MAF and
a self-contained HTML report a clinician can triage without opening a spreadsheet. It annotates
every variant with **Ensembl VEP, ClinVar, ClinGen and the Human Phenotype Ontology**, and in
extended mode with **dbNSFP, 32 VEP plugins and the RENOVO ML pathogenicity classifier**, merges
everything into one row-per-variant table, and ranks the result so the variants worth a second look
surface first.

Built with the [nf-core](https://nf-co.re) pipeline template, on [Nextflow](https://nextflow.io).
Published in *BMC Bioinformatics* — see [Citation](#citation).

![MuSA metro map: the annotate workflow preprocesses a VCF; annotates each variant with Ensembl VEP (plus ClinVar, ClinGen expert-panel classifications, optional VEP plugins and optional GeneBe), dbNSFP and vcf2maf in parallel, merges them and scores RENOVO 1.5; adds gene-level evidence (OMIM, Orphanet, GenCC, HPO, pathways, expression, constraint, ClinGen); then classifies (ClinVar tiers, optional ACMG), filters (optional HPO panel) and writes a per-patient HTML report and MAF; the setup workflow downloads the core and optional VEP plugin databases from a YAML manifest](assets/pipeline_schema.svg)

The report below is real output: MuSA run in extended mode against the paper's own NA12878/HG001
WES-like benchmark VCF (see [Benchmark](#benchmark)). Nothing in it is mocked up.

![MuSA report overview: patient band with ClinVar/RENOVo classification counts and a findings index, next to variant groups such as "ClinVar pathogenic" and "Loss of function in an established disease gene"](docs/images/report_overview.png)

---

## Can you use MuSA?

| | |
|---|---|
| **Genome build** | GRCh38/hg38 only. |
| **Input** | Germline VCFs already called elsewhere (nf-core/sarek, GATK, or any standard multi-caller VCF). MuSA annotates and ranks; it does not call variants. |
| **Compute** | Docker, Singularity or Apptainer. No manual tool installation. |
| **Storage, one-time** | ~30 GB for basic annotation, ~200 GB for extended (dbNSFP, RENOVO 1.5 and 32 VEP plugins). Downloaded once by the `setup` workflow, reused by every `annotate` run. |
| **dbNSFP (extended mode)** | **Academic / non-commercial use only**, and distributed only to registered users: [register at dbnsfp.org](https://www.dbnsfp.org/download) (institutional email) to get your download link before running `setup --extended true`. Basic mode does not need it. |
| **GeneBe (optional)** | Only needed for online-mode ACMG/AMP scoring. Free account at [genebe.net](https://genebe.net/signup). Offline mode (the default) does not need it; HPO matching runs offline. |
| **License** | MuSA itself is [CC BY-NC 4.0](LICENSE) — non-commercial use and redistribution, with attribution. |

If your VCFs are hg38, you can get Docker or Singularity running, and 30 GB of disk is available:
MuSA is feasible for you. If any of those don't hold, see [Requirements](#requirements-and-constraints)
before going further.

---

## Why MuSA?

A germline VCF from a research or diagnostic exome/genome typically needs several tools before a
clinician can read it: a functional-consequence predictor, a set of pathogenicity scores, ClinVar,
a gene-disease evidence source, and some way to fold "unaffected by ClinVar but the phenotype fits"
into a ranking. Running these tools separately means reconciling different variant identifiers,
different transcript choices, and different output formats — and re-doing that reconciliation for
every patient.

MuSA runs the annotation branches in parallel and resolves the disagreements once, in the pipeline,
rather than leaving them for a reviewer to spot:

- **One transcript per variant.** VEP/dbNSFP report scores per transcript; MuSA collapses each
  variant to its MANE Select transcript (configurable) so a gene symbol and a score never come from
  two different isoforms.
- **One classification per variant.** RENOVO's six-class ML output and ClinVar's five-tier
  classification are read onto the same B / LB / VUS / LP / P scale, so "ClinVar disagrees with
  ReNOVo" is something the pipeline can flag, not something a reviewer has to notice by reading two
  differently-formatted columns.
- **Rarity and disease relevance are the filter, not a spreadsheet macro.** Gene-disease validity
  (ClinGen), inheritance mode, gnomAD constraint (pLI/LOEUF) and the patient's own HPO terms are
  joined onto every row so triage doesn't need a second lookup pass.

The output is one MAF file per patient (not per-transcript VCF rows) and one interactive report that
opens in a browser with no server, no account and no upload — the variant data never leaves the
machine it was generated on.

---

## What MuSA does

Two workflows:

| Workflow | What it does | Run it |
|---|---|---|
| `setup` | Downloads and checksums every annotation database into `--data_dir`. Once per data directory. | before the first `annotate` |
| `annotate` | Annotates VCFs against that data directory, ranks variants, writes MAF + HTML report. | once per batch of patients |

**Annotation sources.** MuSA brings in evidence at two levels and then classifies each variant:

- **Variant level:** Ensembl VEP (with ClinVar and ClinGen expert-panel classifications) and
  vcf2maf; in extended mode also 32 VEP plugins and dbNSFP (pathogenicity predictors, population
  databases, conservation).
- **Gene level:** ClinGen (gene–disease validity, dosage sensitivity, actionability) and the
  patient's HPO terms matched against each gene's; in extended mode also dbNSFP's gene file (OMIM,
  Orphanet, GenCC, pathways, expression, constraint).
- **Classification:** ClinVar tiers and ClinVar evidence at the variant's residue (ACMG PS1/PM5);
  RENOVO 1.5 in extended mode; GeneBe ACMG/AMP criteria in online mode.

<!-- sources:start (generated by bin/musa_sources.py render; edit assets/annotation_sources.yaml) -->
**103 annotation sources**, merged into one row per variant (full list with columns and versions: [`docs/sources.md`](docs/sources.md)):

| Level | Evidence | Sources |
|---|---|---|
| Variant | Consequence and transcript | Ensembl / GENCODE gene models, MANE (NCBI / EMBL-EBI), UniProt (protein identifiers), Protein domains (Pfam, PROSITE, SMART, …), InterPro*, GENCODE Ribo-seq ORFs*, Locus Reference Genomic (LRG)* |
| Variant | Known variants and literature | dbSNP, Ensembl variation phenotypes and literature, GWAS Catalog* |
| Variant | Clinical assertions | ClinVar, ClinGen expert-panel classifications |
| Variant | Population frequency | gnomAD v4.1, gnomAD v2.1.1*, 1000 Genomes phase 3, TOPMed (freeze 8)*, ALFA (NCBI)*, All of Us*, Regeneron Genetics Center Million Exomes*, Archaic hominin genomes* |
| Variant | Pathogenicity predictors | SIFT, SIFT4G*, PolyPhen-2, MutationTaster*, MutationAssessor*, PROVEAN*, VEST4*, MetaSVM*, MetaLR*, MetaRNN*, M-CAP*, REVEL*, MutPred2*, MVP*, gMVP*, MisFit*, MPC*, PrimateAI*, DEOGEN2*, BayesDel*, ClinPred*, LIST-S2*, VARITY*, ESM1b*, AlphaMissense*, PHACTboost*, MutFormer*, MutScore*, popEVE*, ALoFT*, CADD*, DANN*, fathmm-XF*, Eigen*, EVE* |
| Variant | Splicing | SpliceAI*, SpliceVault*, MaxEntScan*, dbscSNV* |
| Variant | Regulatory and functional | ProtVar*, IntAct*, Ensembl Regulatory Build, Enformer*, UTRannotator*, MaveDB*, mutfunc*, Ensembl ancestral alleles*, GRC reference issues* |
| Gene | Gene–disease | Gene2Phenotype (G2P)*, ClinGen gene–disease validity, ClinGen dosage sensitivity, ClinGen actionability, OMIM*, Orphanet*, GenCC*, HPO gene terms (dbNSFP)* |
| Gene | Constraint and dosage | MechPredict*, Dosage sensitivity (Collins 2022)*, gnomAD gene constraint*, ExAC gene constraint*, RVIS*, Gene Damage Index*, LoFtool*, Haploinsufficiency predictions*, Recessive disease genes*, Essential genes* |
| Variant | Conservation | GERP++ / GERP (92 mammals)*, phyloP*, phastCons*, B statistic* |
| Gene | Function and pathways | UniProt (function)*, Gene Ontology*, KEGG*, BioCarta*, ConsensusPathDB*, Gene identifiers (HGNC, NCBI Gene, RefSeq, UCSC)* |
| Gene | Expression | Human Protein Atlas* |
| Gene | Model organisms | MGI (mouse)*, ZFIN (zebrafish)*, Ensembl orthologue phenotypes* |
| Scores | Classification | RENOVO 1.5*, GeneBe ACMG/AMP* |
| Gene | Patient phenotype | Human Phenotype Ontology (ontology and annotations) |

\* extended mode (dbNSFP, RENOVO 1.5, VEP plugins) or online mode (GeneBe) only.
<!-- sources:end -->

**Output**, per patient:

- `<patient>.raw.maf` — every variant, fully annotated, one row per variant.
- `<patient>.filtered.maf` — the same table after panel/HPO/frequency/benign filters. The file to hand a reviewer.
- `<patient>_maf_dashboard.html` — the interactive report (below).

Full column-by-column breakdown: [`docs/output.md`](docs/output.md).

---

## The report

`<patient>_maf_dashboard.html` is a single file — no server, no database, no upload. It embeds the
full variant set as compact, column-oriented JSON and renders it through a virtual scroller, so it
stays fast even at tens of thousands of variants, and it opens directly in a browser on an
air-gapped machine.

It opens on **findings, not a spreadsheet**: variants grouped by why they matter — ClinVar
pathogenic/likely-pathogenic, loss-of-function in a disease gene ClinGen backs with definitive or
strong evidence, biallelic calls with no wild-type allele, ClinVar-uncertain-but-RENOVo-pathogenic,
genes ClinVar has never classified, and cases where the two classifiers disagree. Selecting a
variant opens a full evidence panel beside the list — population frequency, gene-disease
relationship, inheritance, literature, all cross-referenced and clickable (OMIM, PubMed, MONDO,
Orphanet, dbSNP, ClinVar) — without ever covering the list you're comparing it against. The full
variant table, sortable and searchable, is one click away for anyone who wants to see everything
that was annotated rather than only what was flagged.

![MuSA evidence panel for a PAH missense variant: ClinVar and RENOVo both call it pathogenic, with the assessment, gene-disease relationship, LOEUF constraint, and clickable ClinVar/dbSNP/OMIM/MONDO/Orphanet/PubMed identifiers](docs/images/report_evidence_panel.png)

---

## Try it in 10 minutes

The database directory (below) is a one-time, ~30 GB download — it is the actual gate, not a
formality, so budget time for it separately. Once it exists, running MuSA against a new VCF, or
against the bundled single-variant test case, takes minutes.

**1. Install Nextflow** (skip if already installed; MuSA needs version 25.10.0 or later):

```bash
curl -s https://get.nextflow.io | bash
```

Already have Nextflow? Check `nextflow -version`, and run `nextflow self-update` if it is older than 25.10.0.

**2. Build the database directory** — required once, before any `annotate` run:

```bash
nextflow run davide-scognamiglio/MuSA \
  --workflow setup \
  --data_dir /path/to/musa_data \
  -profile docker
```

`--data_dir` must be an absolute path (`$PWD/musa_data`, not `musa_data`): the container engine
mounts it as given, and MuSA stops at startup if it is relative. Use the same path for `setup` and
`annotate`.

This fetches basic mode: VEP's cache, the reference genome, ClinVar, ClinGen and the Human
Phenotype Ontology (~30 GB). Get a coffee; it does not need supervision, and `<data_dir>/setup_report.html` lists
exactly what landed and its checksum when it's done.

**3. Run the bundled test** — a single-variant VCF, so this finishes in a couple of minutes and
proves your Docker and data directory are wired correctly:

```bash
nextflow run davide-scognamiglio/MuSA \
  -profile test,docker \
  --data_dir /path/to/musa_data \
  --outdir output_test
```

Expect `output_test/<date>/NA12877/NA12877_maf_dashboard.html` — open it in a browser.

That's the smallest loop: real containers, a real (if tiny) VCF, a real report. Section
[Pipeline usage](#pipeline-usage) below shows the same command against your own samplesheet.

---

## Requirements and constraints

**Genome build.** hg38/GRCh38 only. The pipeline errors explicitly (`Currently, we only support hg38
build`) rather than silently mis-annotating a GRCh37 VCF — realign or lift over first.

**Storage — two tiers, pick based on what you need:**

| Mode | What it adds | Approx. size | When to use it |
|---|---|---|---|
| **Basic** (default) | VEP cache (consequences, gnomAD, 1000 Genomes, dbSNP), reference genome, ClinVar, ClinGen, Human Phenotype Ontology | ~30 GB | Consequence, frequency, clinical significance, gene-disease validity, phenotype match. No registration needed |
| **Extended** (`--extended true`) | + dbNSFP (~35 predictors, gene file with OMIM/Orphanet/constraint), RENOVO 1.5, all 32 VEP plugins and their data (AlphaMissense, CADD, SpliceAI, Enformer, EVE, SpliceVault, ProtVar, G2P, ...) | ~200 GB total | Deep annotation: in-silico predictions and RENOVO classes. dbNSFP needs a registration |

The same `--extended true` switches `setup` (download) and `annotate` (use). An extended `annotate`
stops at startup if the data directory has no dbNSFP.

**RENOVO scores come from RENOVO 1.5, in extended mode.** MuSA scores variants with
[renovo-rebuild](https://github.com/davide-scognamiglio/renovo-rebuild), which runs RENOVO's
published model on MuSA's own annotations instead of an ANNOVAR re-annotation. Discrimination is
unchanged within 0.001 AUC on ClinVar variants RENOVO never saw, but individual scores differ from
the original software, so do not compare `RENOVO_Class` across MuSA 1.1 and 1.2 results. RENOVO is
non-commercial software; commercial use needs the RENOVO authors' permission. Eight of its thirteen
inputs are dbNSFP scores, so it runs only with `--extended true`.

**dbNSFP (extended mode) is academic-use only, and you download it with your own registration.**
dbNSFP's academic distribution (CC BY-NC-ND 4.0) is handed out per registered user, so the manifest
names the version and its SHA-256 but no URL: register at [dbnsfp.org](https://www.dbnsfp.org/download)
with your institutional email and give `setup --extended true` your link (`--dbnsfp_url`, quoted; it
is kept out of the parameter summary) or the zip (`--dbnsfp_zip /path/to/dbNSFP5.3.1a.zip`). Either
way the file is checked against the manifest's SHA-256. Confirm the license
covers your use case — this is a constraint on the data, not something MuSA can relax.

**GeneBe is optional and needs credentials.** Only relevant if you run with `--offline false` for
automated ACMG/AMP scoring. Offline mode — the default — makes no outbound network calls; HPO
matching uses the HPO release `setup` installs.

**MuSA's own license is CC BY-NC 4.0** — non-commercial use and redistribution with attribution. See
[LICENSE](LICENSE).

---

## Installation / setup

### Which version?

Three releases are maintained. All three receive stability fixes; only the newest receives new
features. Pick one with `-r`:

| Release | Use it to | Run with |
|---|---|---|
| **1.2.0** (latest) | start new analyses: RENOVO 1.5 scores, no ANNOVAR needed | `-r v1.2.0` |
| **1.1.0** | reproduce results made with 1.1 (ANNOVAR-based RENOVO) | `-r v1.1.0` |
| **1.0.0** | run the version described in the [paper](https://doi.org/10.1186/s12859-026-06513-0) | `-r v1.0.0` |

`v1.0.0` and `v1.1.0` were updated in place on 2026-09-24 with stability and correctness fixes (see
[CHANGELOG](CHANGELOG.md)). If you ran either before that date, refresh Nextflow's copy of the
pipeline once with `nextflow drop davide-scognamiglio/MuSA`. Each release downloads the databases
it was built for, from a manifest pinned in
[test-datasets](https://github.com/davide-scognamiglio/test-datasets).

Prerequisites: [Nextflow ≥ 25.10.0](https://nextflow.io) and Docker or Singularity/Apptainer.

> [!NOTE]
> On an older Nextflow, MuSA stops before running anything with
> `Plugin nf-schema with version @2.7.3 does not exist in the repository`. Nextflow 25.04 and
> earlier read an older plugin index that doesn't list the nf-schema versions MuSA needs. Run
> `nextflow self-update`, or pin a version for one run with `NXF_VER=25.10.2 nextflow run ...`.

```bash
nextflow run davide-scognamiglio/MuSA \
  --workflow setup \
  --data_dir /path/to/musa_data \
  -profile docker            # or -profile singularity
```

`--data_dir` must be an absolute path; MuSA stops at startup if it is relative.

Add `--extended true --dbnsfp_url '<your dbNSFP download link>'` for the extended (~200 GB) tier;
on a basic data directory it downloads only what extended mode adds. Re-running `setup` later only
re-downloads entries whose manifest version changed (`--update_db_only true` to force a diff-only
refresh).

Every downloaded resource is tracked in a versioned, checksummed manifest — see
[The database manifest system](docs/usage.md#setup-workflow) for how that works and why it matters
for audit trails. Full parameter reference: [`docs/usage.md`](docs/usage.md) and
[`nextflow_schema.json`](nextflow_schema.json) (or run with `--help`).

---

## Pipeline usage

**1. Samplesheet** — one row per patient:

```csv title="samplesheet.csv"
patient,sample_type,sample_file,hpo
PATIENT_01,blood,/path/to/PATIENT_01.vcf.gz,HP:0001250;HP:0002121
PATIENT_02,saliva,/path/to/PATIENT_02.vcf.gz,
```

| Column | Required | Description |
|---|---|---|
| `patient` | yes | Identifier. Names the output directory and every output file. |
| `sample_type` | yes | Free-text sample source (`blood`, `saliva`, ...). Informational. |
| `sample_file` | yes | Path to the VCF, `.vcf` or `.vcf.gz`. |
| `hpo` | no | `;`-separated HPO term IDs. Each gene is matched against them (exact, narrower or broader, with a similarity score and the best-matching disease), and genes that match a specific term make up a phenotype panel for the filtered MAF; leave empty to skip. |

**2. Run** — offline mode (default; no network calls, local databases only):

```bash
nextflow run davide-scognamiglio/MuSA \
  --workflow annotate \
  --input samplesheet.csv \
  --outdir results \
  --data_dir /path/to/musa_data \
  --vcf_format multicaller \
  -profile docker
```

Add `--extended true` for extended annotation (needs the extended `setup`), or
`--offline false --gb_user <user> --gb_api_key <key>` for GeneBe ACMG/AMP scoring. Full walkthrough, including proxy configuration and params files:
[`docs/usage.md`](docs/usage.md).

**3. Output** — `results/<date>/<patient>/`, one directory per patient:

```
results/
└── 260907/
    └── PATIENT_01/
        ├── PATIENT_01_maf_dashboard.html
        ├── PATIENT_01.filtered.maf
        └── PATIENT_01.raw.maf
```

Column-by-column breakdown of what's in the MAF: [`docs/output.md`](docs/output.md).

---

## Benchmark

Same dataset, same in-house server (Intel Xeon Gold 6444Y, 64 cores, 250 GB RAM), two pipeline
versions: a downsampled, WES-like NA12878/HG001 (GRCh38) callset, ~22,700 variants, full
extended-mode annotation (all 22 VEP plugins MuSA 1.1 used).

| Version | Wall time | CPU time |
|---|---|---|
| v1.0.0 (paper-published figure) | ~20 minutes | — |
| v1.1.0 | **3m 23s** | 0.8 CPU-hours |

The difference is dbNSFP, not the hardware: in v1.0.0 it ran as a single pass over the whole VCF,
which dominated wall time; v1.1.0 shards the VCF by chromosome and annotates the shards in
parallel. Everything else about the run is the same dataset, mode and machine.

This is a fixed reference point on fixed hardware, not a guarantee — your runtime scales with core
count, VCF size, and whether you run basic or extended mode. Per-task resource use for any of your
own runs is in `<outdir>/pipeline_info/execution_trace_*.txt`.

---

## Citation

If you use MuSA, please cite:

> Scognamiglio D, Bonetti E, Moroni A, Sangiorgi L, Pedrini E. MuSA: a Nextflow pipeline for deep,
> reproducible annotation and clinical ranking of genomic variants. *BMC Bioinformatics*. 2026 Jun
> 16;27(1):199. doi: [10.1186/s12859-026-06513-0](https://doi.org/10.1186/s12859-026-06513-0).

An extensive list of references for every tool the pipeline uses is in
[`CITATIONS.md`](CITATIONS.md).

---

## License, acknowledgements, contact

MuSA is licensed under [CC BY-NC 4.0](LICENSE) — non-commercial use and redistribution, with
attribution.

Written by D. Scognamiglio and E. Bonetti at IRCCS Istituto Ortopedico Rizzoli, Bologna, Italy, with
contributions from A. Moroni, L. Sangiorgi and E. Pedrini. Built with the
[nf-core](https://nf-co.re) pipeline template; thanks to that community for the tooling and
conventions MuSA's development leaned on.

Questions or issues: [open a GitHub issue](https://github.com/davide-scognamiglio/MuSA/issues).
