# MuSA: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### `Changed`

- The README's pipeline diagram is now an animated nf-metro map covering both workflows,
  `annotate` (ending in the HTML report and the MAF) and `setup`, with optional steps marked.
- Refreshed the README logos.

### `Removed`

- nf-core template leftovers MuSA never used: the Slack and Teams notification templates,
  `tower.yml` (a Seqera report for a samplesheet MuSA does not publish) and the example
  `assets/samplesheet.csv`.
- Stray development files: `assets/clingen_manifest_entries.yaml`, `conf/custom_annotation.config`,
  an unreferenced `tests/config/test.config`, `docs/images/test.txt`, and the old `v1.0` banner
  PNGs under `assets/`.

## v1.1.0 - 2026-09-10

First tagged release since the paper's submitted state. Three threads: the annotation engine
gained ClinGen and gene-level dbNSFP context and fixed two correctness bugs in the merge; the
per-patient HTML report was rebuilt from a static table into a findings-first clinical review
tool; and the pipeline's nf-core compliance, CI and documentation were brought up to a state that
actually lints and actually reflects what the code does.

### `Added`

- ClinGen annotation: dosage sensitivity, gene-disease validity and VCEP curation, joined onto
  the merged MAF.
- dbNSFP gene-level columns (pLI, LOEUF, disease/phenotype cross-references), parallelised
  per-chromosome.
- Per-transcript dbNSFP scores resolved to one value per variant via the MANE Select transcript
  (`--dbnsfp_transcript_scores`), instead of leaving `;`-delimited arrays for the reader to
  positionally decode.
- GWAS and pLI VEP plugins wired and consumed; the "22 VEP plugins" figure is now true rather
  than aspirational. The unsupported SpliceAI claim was removed rather than left inaccurate.
- VEP bumped 115.2 -> 116.2, pointed at the official `ensemblorg/ensembl-vep` image rather than a
  dsbioinfo retag; the cache the manifest fetches now matches it. Verified before switching: every
  plugin this pipeline wires ships unchanged in 116.2, and a real annotation run against all of
  them produced a byte-identical CSQ schema and values on the bundled test VCF. `params.vep_container`
  is the single declaration both the annotation module and the report's provenance line read, so
  this is a one-place change.
- Manifest-driven database updates: `setup` can now re-download only the entries whose version
  changed (`--update_db_only`), instead of always refetching everything.
- The annotation report rebuilt end to end: opens on findings grouped by why a variant matters
  (ClinVar pathogenic, loss-of-function in an established disease gene, biallelic calls,
  ClinVar/RENOVo disagreement, unclassified-but-RENOVo-pathogenic) rather than a raw variant
  table; a docked evidence panel with every identifier (OMIM, PubMed, MONDO, Orphanet, dbSNP,
  ClinVar) rendered as a live link; a sticky summary band carrying the review-set counts, VEP and
  ClinVar release versions, the patient's HPO terms (linked to hpo.jax.org), and a clickable index
  of the findings blocks; Poppins typography and a real light/dark palette in place of the
  previous unstyled table. The setup report was brought to the same standard: its plain
  four-number integrity block and proportional bar became a case-identity band with bordered
  count boxes, sharing the band system extracted into `musa_report_style.BAND_CSS` rather than
  drifting into its own look. Both reports stay fully self-contained -- no network access at read
  time.
- The publication citation, DOI badge and a GitHub link added to both reports' masthead/footer.
- `docs/usage.md` and `docs/output.md` rewritten from scratch against the pipeline MuSA actually
  is (the templated versions described a FastQ/RNA-seq pipeline). `README.md` rewritten as a
  landing page, with real report screenshots generated from the paper's own NA12878/HG001
  WES-like benchmark VCF.

### `Fixed`

- **Correctness:** the dbNSFP-to-MAF merge could emit more than one row per variant; collapsed to
  one row, keeping the VEP-picked transcript. RENOVO predictions were aligned back to variants by
  row position rather than by label, which silently mismatched under reordering; now aligned by
  label. VEP's most-severe-consequence selection and CSQ-as-first-INFO-field parsing were both
  wrong in edge cases.
- **Data quality:** `NA`, empty cells and `.` were three different spellings of "missing" across
  the final MAF; normalised to `.` everywhere.
- **Resourcing:** RENOVO's memory request was sized from a bad-BED outlier rather than the
  measured real-exome peak, which either wasted memory or courted an OOM depending on which side
  of the outlier a run landed on; resized from the actual measured cohort peak (26.0 GB).
  `ADD_REF_CONTEXT` OOM-killed on a WGS-scale callset (3.9M variants): it materialised the whole
  pre-merge MAF as a list of Python dicts and reopened the reference FASTA on every row. Rewritten
  to stream row by row and open the FASTA once; verified on the exact input that crashed it (62s,
  under a 1.5 GB memory cap, versus OOM at 16 GB and climbing).
- **Security:** GeneBe credentials and the HTTP(S) proxy were hardcoded in config; now read from
  environment variables.
- **Pipeline robustness:** a bad samplesheet used to kill the JVM directly (`System.exit(1)`),
  orphaning any already-dispatched containerised tasks; now aborts cleanly through Nextflow's own
  error path. A vacuous schema conditional meant omitting `--workflow` silently triggered the
  `annotate` validation branch. `--help` did not work, despite being documented, because nothing
  wired nf-schema's help into `main.nf`.
- **nf-core compliance:** the release lint could not run at all -- three crashes fired before a
  single check executed, on every PR, not just releases (`manifest.name` without an org prefix,
  a missing `pre-commit` dependency in CI, an unguarded schema `$ref`). Fixed the two that were
  genuine bugs and declared the third a documented divergence rather than papering over it.
  Branch protection was comparing against a repository name that could never match, so it had
  never once fired. Several `owner-less` `github.com/MuSA` URLs (issue/PR templates, email
  templates, the failed-CI comment link) pointed nowhere; corrected to the real repository.
  `conf/test.config` had rotted to a viralrecon yeast samplesheet with a 15 GB resource cap that
  would have silently reintroduced a known RENOVO OOM had anything ever included it; now MuSA-real
  and wired to the `test`/`test_full` profiles.
- A findings-report layout bug where the evidence panel's top edge did not line up with the first
  findings block. A stray Groovy-style `//` comment inside a bash `script:` block (harmless in
  practice, wrong in principle).

### `Dependencies`

- VEP plugin data: added GWAS-catalog and pLI value tables (consumed by the newly-wired plugins
  above).

### `Deprecated`

Nothing removed in this release.
