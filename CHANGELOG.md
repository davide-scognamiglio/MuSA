# MuSA: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.2.0 - 2026-09-24

RENOVO scores from renovo-rebuild (RENOVO 1.5) and no more ANNOVAR, plus the setup and
Nextflow-compatibility fixes, which were also applied retroactively to v1.1.0 and v1.0.0.

### `Fixed`

- **`setup` installed nothing.** Every download module built its directory in the task work dir and
  relied on `publishDir` with a `pattern:` to copy it into `--data_dir`, but `publishDir` only
  publishes files a process declares as outputs, and `8871db4` (2026-07-14) removed those
  declarations. Since then a fresh `setup` downloaded tens of GB, left them in `work/`, and the
  first step reading the data directory failed with
  `No such file or directory: <data_dir>/vep_data/reference_genome/hg38.fa.fai`. Only ClinVar and
  ClinGen were unaffected, because they already installed into the bind-mounted `/data` themselves.
  All 19 remaining modules now do the same through a shared `install_into_data` helper, which stages
  the directory and renames it into place so an interrupted install cannot leave a half-populated
  folder that the next run's skip check would accept. Installed files are handed to the owner of
  `--data_dir` (the docker and podman profiles run tasks as root), so they stay editable without
  sudo and later steps can publish into them. Existing data directories are unaffected.
- **A failed download was installed as if it had worked.** `download_and_compute_sha` did not check
  the exit status of `wget`/`curl`/`gdown`: because it runs inside a command substitution, a failure
  did not stop the task, so a blocked or refused download left a 0-byte file that was hashed,
  written into the manifest and installed. The helper now fails the task when the download command
  reports an error or produces no data.
- **Large downloads gave up when the server dropped the connection.** `wget` resumed at most 5
  times and `curl` never resumed (its `--retry` restarts from zero and does not retry a transfer cut
  mid-way), so dbNSFP (~47 GB) failed at 27.9 GB after 1h35m on a host that closes long
  connections. Both now resume from the bytes already on disk, up to 100 times; HTTP errors such
  as 403/404 still fail after 3 attempts.
- **dbNSFP could never finish downloading on a normal link.** Every process inherits `time = 2.h`
  from `nextflow.config`, and a 45 GB download at a few MB/s outlives it: Nextflow killed the task
  at 83% ("process hasn't exited"), and a retry would restart from zero. `DOWNLOAD_*` processes now
  get 72 h.
- MuSA runs on current Nextflow again. Nextflow 26.04 turns on its strict syntax by default, and
  MuSA's config and scripts used constructs it rejects (`def` inside profile blocks, `switch`,
  `while`, `++`, statements outside the workflow block, an input variable in a `publishDir`
  string). Rewritten in forms both the old and the strict parser accept. A test-profile run on
  26.04.6 produces MAFs and a report byte-identical to the unmodified code on 25.10.2.
- `annotate` with `-profile docker` and no proxy crashed in VEP. The profile always passed
  `-e http_proxy=${params.http_proxy}`, which becomes the literal string `null` when no proxy is
  set, and the official VEP 116 image refuses it ("Proxy must be specified as absolute URI").
  The proxy variables are now passed only when set.
- The minimum Nextflow version is now stated correctly as 25.10.0 (manifest, README, CI). The
  nf-schema plugin MuSA pins has required 25.10 since v1.1.0, and Nextflow 25.04 failed with
  `Plugin nf-schema with version @... does not exist in the repository`. nf-schema moves from
  2.6.1 to 2.7.3, whose `--help` also works on Nextflow 26.04.
- MuSA no longer depends on the host's tools. `PARSE_VEP_ANNOTATION`, `RENAME_VCF_BY_PATIENT` and
  `BUILD_SETUP_REPORT` declared no container and ran directly on the host, so they needed host
  `python3` and gawk: `PARSE_VEP_ANNOTATION`'s awk used gawk-only `match()` capture arrays, which
  fail with a syntax error under mawk, the awk a stock Ubuntu install ships. All three now run in
  the MuSA helper images, and the awk is rewritten in POSIX form. On real NA12878 VEP output (up to
  1.06 million rows) the rewrite under mawk gives byte-identical output to the original under gawk.
- A default container set for all pipelines in `~/.nextflow/config` (for example
  `process.container = "ubuntu:22.04"`) stopped MuSA before its first task with
  `Cannot cast object ... to class 'java.util.Map'`, a crash in nf-schema's parameter summary.
  MuSA's config now clears that default; every MuSA module declares its own container.
- `setup` with a `--data_dir` that did not exist yet failed at the end. Docker created the missing
  folder as root, and Nextflow could not publish `setup_report.html` into it. `setup` now creates
  `--data_dir` as the launching user before any task starts.

### `Changed`

- **RENOVO scores now come from renovo-rebuild (RENOVO 1.5), and ANNOVAR is no longer used.**
  [renovo-rebuild](https://github.com/davide-scognamiglio/renovo-rebuild) runs RENOVO's published
  random forest, unchanged, on columns MuSA already annotates (VEP consequence and gnomAD 4.1 AF,
  dbNSFP 5 scores, MuSA's ClinVar) instead of re-annotating every VCF with ANNOVAR. The new
  `RENOVO_SCORE` step scores the merged table after `MERGE_ANNOTATIONS`; the parallel
  `RENOVO_ANNOTATE_VCF` branch is gone. Per exome it takes seconds and under 0.5 GB of memory,
  against about 3.5 minutes and 21-24 GB before.
  Scores are not identical to MuSA 1.1: dbNSFP 5 retired FATHMM and fathmm-MKL and replaced MutPred
  with MutPred2, so those inputs use fathmm-XF, MutPred2 or RENOVO's own per-Type median, and
  RENOVO's ANNOVAR `Type` is derived from VEP's picked transcript. On 251,297 ClinVar variants
  absent from RENOVO's training data: AUC 0.995 vs 0.996, sensitivity 0.969 vs 0.975, specificity
  0.991 vs 0.991; 99.0% of variants stay on the same side of the 0.5 benign/pathogenic threshold
  and 83.8% keep the exact class. Do not compare `RENOVO_Class` across 1.1 and 1.2 results.
- The raw MAF loses the columns only ANNOVAR produced (104 in the test profile): gnomAD 2.1.1
  sub-population frequencies, dbNSFP 3.5c score copies, refGene/ensGene `Func`/`ExonicFunc`/
  `AAChange`, `avsnp150`, InterVar's 2018 automated ACMG criteria and the `Otherinfo*` columns.
  VEP and dbNSFP 5 already carry current equivalents; `rs_dbSNP` (dbNSFP) is now kept in place of
  `avsnp150`. None of the removed columns was read by the report, the filters or the ACMG step.
- The README's pipeline diagram is now an animated nf-metro map covering both workflows,
  `annotate` (ending in the HTML report and the MAF) and `setup`, with optional steps marked.
- Refreshed the README logos.

### `Removed`

- ANNOVAR: the `--annovar_software_dir` parameter and its container bind, the ANNOVAR database
  download in `setup` (51 GB, `renovo_humandb/`), the `RENOVO_ANNOTATE_VCF` module and the patched
  RENOVO image source (`containers/renovo`). A basic `setup` is now about 72 GB, extended about
  173 GB. Existing data directories keep working; `renovo_humandb/` can be deleted.
- `bin/acmg_classifier.R`, an unused stub and the only other reader of the InterVar columns.
- nf-core template leftovers MuSA never used: the Slack and Teams notification templates,
  `tower.yml` (a Seqera report for a samplesheet MuSA does not publish) and the example
  `assets/samplesheet.csv`.
- Stray development files: `assets/clingen_manifest_entries.yaml`, `conf/custom_annotation.config`,
  an unreferenced `tests/config/test.config`, `docs/images/test.txt`, and the old `v1.0` banner
  PNGs under `assets/`.

## v1.1.0 - 2026-09-10

> Re-released in place on 2026-09-24 with the setup and Nextflow fixes listed under v1.2.0
> (all except the RENOVO/ANNOVAR changes). The `v1.1.0` tag's own CHANGELOG lists them.

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
