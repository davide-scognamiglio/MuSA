# MuSA: Changelog

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v1.0.0 - 2026-05-27, fixed 2026-09-24

The version described in the paper. On 2026-09-24 the `v1.0.0` tag was moved to this fixed code:
bug fixes from 1.1.0 and 1.2.0 backported, no new features. The code exactly as published is
commit `bb0d39c`. If you ran v1.0.0 before 2026-09-24, run `nextflow drop davide-scognamiglio/MuSA`
once so Nextflow fetches the updated tag.

### `Changed`

- The default `--dbs_manifest` now points to the test-datasets commit this release was built for
  (`13b203d`) instead of `main`.
  `main` follows the newest MuSA and lists the VEP 116 cache, which 1.0's VEP 115.2 cannot use, so
  a fresh 1.0 setup downloaded a cache its annotation step could not read.
- Minimum Nextflow is 25.10.0 (was stated as 25.04.0, which never worked: the pinned nf-schema
  plugin requires 25.10). nf-schema 2.6.1 -> 2.7.3.

### `Fixed`

Annotation correctness (from 1.1.0). These change results where the published code was wrong:

- VEP picked the transcript by MANE/canonical status before consequence severity, so in regions
  where genes overlap it could report a neighbouring gene's MODIFIER consequence instead of the
  real one (on a 30,202-variant ClinVar sample: 5.4% of coding variants lost their consequence,
  7.4% got the wrong gene). Severity now decides; MANE/canonical only break ties. CSQ written as
  the first INFO field was not parsed, leaving every VEP column `NA` for VCFs with an empty INFO.
- The dbNSFP merge emitted one MAF row per dbNSFP isoform row, duplicating variants whose isoforms
  differ in reading frame, with scores from an isoform VEP had not picked. Now one row per variant,
  keeping the VEP-picked isoform.
- RENOVO assigned predictions to rows by position, so an unscorable row shifted every later
  prediction onto the wrong variant, and two adjacent unscorable rows crashed the step. Predictions
  are now matched by row label (`dsbioinfo/renovo:1.1.2`).
- `ADD_REF_CONTEXT` loaded the whole MAF into memory and was OOM-killed on WGS-scale input; it now
  streams.

Stability (from 1.2.0):

- MuSA runs on Nextflow 26.04, whose strict syntax is the default: config and scripts rewritten in
  forms both parsers accept.
- `-profile docker` without a proxy passed the literal string `null` as `http_proxy`, which VEP
  rejects. Proxy variables are now passed only when set.
- Three modules ran on the host and needed its `python3` and gawk; they now run in containers, and
  the VEP-parsing awk is POSIX, so it works under mawk (stock Ubuntu).
- A default container set in `~/.nextflow/config` crashed MuSA before its first task.
- `setup` with a `--data_dir` that did not exist left it root-owned, so publishing into it failed.
- A failed download left a 0-byte file that was checksummed and installed as the database; the
  task now fails. Downloads resume after a dropped or stalled connection (up to 100 times) instead
  of giving up or restarting from zero, and database downloads get 72 h instead of the 2 h default,
  which killed the 45 GB dbNSFP download on an ordinary connection.
- A bad samplesheet stopped the JVM with `System.exit(1)`, orphaning running tasks; it now fails
  through Nextflow's error path. `-profile test` only worked from inside a clone of the repository.
- Removed an unused `check_max()` helper whose limits were never applied.
