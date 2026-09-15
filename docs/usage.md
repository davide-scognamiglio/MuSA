# MuSA: Usage

## Introduction

MuSA annotates germline small variants and ranks them for clinical review. It takes **VCFs** — not
reads — so it sits downstream of whatever called your variants (nf-core/sarek, DRAGEN, GATK, a
clinical pipeline). It is restricted to **hg38**.

The pipeline has two workflows, selected with `--workflow`:

| Workflow | Purpose |
|---|---|
| `setup` | Downloads and verifies every annotation resource. Run once per data directory. |
| `annotate` | Annotates VCFs and produces the MAF files and HTML reports. |

`setup` must complete before `annotate` will work.

## Setup workflow

Run this first. It populates `--data_dir` with the VEP cache, the native dbNSFP distribution,
ClinVar/ClinGen, and the reference genome, recording a SHA-256 checksum for each in a versioned
manifest.

```bash
nextflow run MuSA \
   --workflow setup \
   --data_dir /path/to/musa_data \
   -profile docker
```

**Basic setup** (the command above) fetches what routine diagnostics needs: ~72 GB.

**Extended setup** additionally fetches the data files for all 22 VEP plugins, bringing the total to
~173 GB. Required before `--use_vep_plugins true`:

```bash
nextflow run MuSA \
   --workflow setup \
   --data_dir /path/to/musa_data \
   --download_vep_plugins true \
   -profile docker
```

When setup finishes, `<data_dir>/setup_report.html` lists every resource with its version, source
and checksum, marked `VERIFIED`, `MISMATCH` or `PENDING`.

To refresh databases later without re-downloading what has not changed, add `--update_db_only true`.
The manifest is diffed against what is already on disk and only changed entries are fetched.

## Samplesheet input

`annotate` takes a comma-separated samplesheet with a header row:

```bash
--input '[path to samplesheet file]'
```

```csv title="samplesheet.csv"
patient,sample_type,sample_file,hpo
5510,blood,/data/vcf/5510.vcf.gz,HP:0002650;HP:0000926
5724,blood,/data/vcf/5724.vcf.gz,
```

| Column | Required | Description |
|---|---|---|
| `patient` | yes | Patient identifier. Names the output directory and every output file. |
| `sample_type` | yes | Free-text sample source, e.g. `blood`, `saliva`. |
| `sample_file` | yes | Path to the VCF. Must end `.vcf` or `.vcf.gz`. |
| `hpo` | no | `;`-separated HPO term IDs, e.g. `HP:0002650;HP:0000926`. Drives phenotype-based gene-panel filtering; leave empty to skip it for that patient. |

One row per patient.

## Running the pipeline

```bash
nextflow run MuSA \
   --workflow annotate \
   --input ./samplesheet.csv \
   --outdir ./results \
   --data_dir /path/to/musa_data \
   -profile docker
```

Results land in `<outdir>/<date>/<patient>/` — see [output.md](output.md).

### Basic and extended annotation

Basic annotation is the default. To use the full plugin suite (requires extended setup):

```bash
nextflow run MuSA \
   --workflow annotate \
   --input ./samplesheet.csv \
   --outdir ./results \
   --data_dir /path/to/musa_data \
   --use_vep_plugins true \
   -profile docker
```

### Online mode and ACMG/AMP classification

MuSA runs offline by default. Automated ACMG/AMP classification is retrieved from the GeneBe
knowledgebase, which needs network access and credentials:

```bash
--offline false --gb_user <user> --gb_api_key <key>
```

Behind a proxy, add `--http_proxy` / `--https_proxy`. To keep online mode but skip GeneBe (for
instance when the API is rate-limited), add `--skip_genebe true`.

> [!NOTE]
> Online mode sends variant coordinates to an external service. HPO-driven filtering also queries
> the HPO API. Everything else runs against local databases.

### Filtering

The filtered MAF is produced by three filters, all optional and independently applicable:

| Parameter | Default | Description |
|---|---|---|
| `--panel` | `null` | Name of a gene panel CSV under `<data_dir>/panels` (without the `.csv`). Restricts output to those genes. |
| `--max_freq` | `null` | Drop variants above this population allele frequency, e.g. `0.05`. |
| `--drop_benign` | `false` | Drop variants ClinVar reports as benign. |

The samplesheet's `hpo` column adds a fourth, per-patient: genes associated with those HPO terms are
retrieved from the HPO API and used as an additional panel.

### Other parameters

| Parameter | Default | Description |
|---|---|---|
| `--build` | `hg38` | Reference build. Only `hg38` is supported. |
| `--vcf_format` | `null` | Set to `sarek` for VCFs from nf-core/sarek so its hard-filter conventions are applied. |
| `--skip_bcftools` | `false` | Skip bcftools normalisation, for input already normalised and left-aligned. |
| `--n_core` | `8` | Cores given to VEP and other per-sample steps. |
| `--dbnsfp_max_forks` | `16` | Concurrent dbNSFP per-chromosome shards. Lower it if memory is tight. |
| `--dbnsfp_transcript_scores` | `mane` | How to resolve dbNSFP's per-transcript score arrays to one value per variant. |

The full list is in [`nextflow_schema.json`](../nextflow_schema.json), or run with `--help`.

#### dbNSFP transcript-specific scores

dbNSFP reports many scores **per transcript**, as `;`-delimited arrays positionally aligned with
`Ensembl_transcriptid`:

```
Ensembl_transcriptid   ENST00000538872;ENST00000382841;ENST00000111111
MANE_dbNSFP            .;Select;.
SIFT_score             0.622;1.0;0.3
REVEL_score            0.361;0.361;0.9
```

Read on its own, `SIFT_score` is ambiguous: nothing in that field says which of the three numbers
belongs to the isoform you care about. The position of the canonical isoform is encoded **only** in
`MANE_dbNSFP` — the offset of `Select` is the offset to read in every other array.
`Ensembl_transcriptid` names the transcript at each position but does not mark which one is
canonical, and `Feature` (VEP's pick) is the most-severe-consequence transcript, which is not
necessarily the MANE one.

`Feature`, `Ensembl_transcriptid` and `MANE_dbNSFP` are all preserved in the final MAF, in either
mode. They answer different questions and none substitutes for another: `Feature` is the single
transcript VEP/vcf2maf selected, and the row's `HGVSc`/`HGVSp`/`Consequence` are expressed against
it; `Ensembl_transcriptid` is the transcript mapping of dbNSFP's own annotations — positional under
`all`, and under `mane` collapsed in lockstep with the scores so it names the one transcript they
came from; `MANE_dbNSFP` marks which position is canonical. Keeping all three lets a downstream
consumer resolve transcript-specific scores explicitly while still seeing dbNSFP's original
annotation.

| Value | Behaviour |
|-------|-----------|
| `mane` (default) | Every transcript-aligned column is rewritten to the single element at the MANE position, so each score column holds one value. When a variant has no MANE transcript the pipeline falls back, in order, to MANE Plus Clinical → the transcript VEP picked (`Feature`) → the first element. One index is chosen per row and applied to every column, so columns can never disagree. `MANE_dbNSFP` is collapsed along with the rest and doubles as a provenance flag: `.` means the scores on that row did **not** come from a MANE transcript. |
| `all` | Arrays are left exactly as dbNSFP produced them. Use this if you would rather resolve transcripts yourself downstream — `Ensembl_transcriptid` and `MANE_dbNSFP` give you everything needed to do so. |

Which columns count as transcript-aligned comes from a fixed, committed list
(`assets/dbnsfp_transcript_aligned_columns.txt`), not from inspecting each run's output. dbNSFP also
uses `;` for gene-level fields (`GO_*`, `Pathway(*)`, `HPO_*`, `MIM_*`, `Orphanet_*`, `GenCC_*`) whose
element count has nothing to do with transcripts, and a per-file guess would collapse a column for
one patient but not the next. As a second safeguard, a value is rewritten only when its element count
matches that row's transcript count. Regenerate the list after a dbNSFP upgrade with
`bin/gen_dbnsfp_aligned_columns.py`.

### Params files

Rather than repeating flags, put them in a params file:

```bash
nextflow run MuSA -profile docker -params-file params.yaml
```

```yaml title="params.yaml"
workflow: 'annotate'
input: './samplesheet.csv'
outdir: './results'
data_dir: '/path/to/musa_data'
use_vep_plugins: true
```

> [!WARNING]
> Do not use `-c <file>` to specify parameters — that will error. `-c` is only for tuning process
> resources, infrastructure settings, or module arguments.

Note that the pipeline creates the following in your working directory:

```bash
work                # Nextflow working files
<OUTDIR>            # Results, as given by --outdir
.nextflow_log       # Nextflow log
```

### Updating the pipeline

```bash
nextflow pull davide-scognamiglio/MuSA
```

### Reproducibility

Pin the pipeline version so a rerun uses the same code. Find the version on the
[MuSA releases page](https://github.com/davide-scognamiglio/MuSA/releases) and pass it with `-r`:

```bash
nextflow run davide-scognamiglio/MuSA -r 1.0 ...
```

Pin the *data* as well as the code: keep the merged manifest written by the setup workflow. It
records the exact version and checksum of every database an annotation was produced against, which
the pipeline version alone does not capture.

## Core Nextflow arguments

> [!NOTE]
> These options are part of Nextflow and use a _single_ hyphen (pipeline parameters use a double-hyphen)

### `-profile`

Use this parameter to choose a configuration profile. Profiles can give configuration presets for different compute environments.

Several generic profiles are bundled with the pipeline which instruct the pipeline to use software packaged using different methods (Docker, Singularity, Podman, Shifter, Charliecloud, Apptainer, Conda) - see below.

> [!IMPORTANT]
> We highly recommend the use of Docker or Singularity containers for full pipeline reproducibility, however when this is not possible, Conda is also supported.

The pipeline also dynamically loads configurations from [https://github.com/nf-core/configs](https://github.com/nf-core/configs) when it runs, making multiple config profiles for various institutional clusters available at run time. For more information and to check if your system is supported, please see the [nf-core/configs documentation](https://github.com/nf-core/configs#documentation).

Note that multiple profiles can be loaded, for example: `-profile test,docker` - the order of arguments is important!
They are loaded in sequence, so later profiles can overwrite earlier profiles.

If `-profile` is not specified, the pipeline will run locally and expect all software to be installed and available on the `PATH`. This is _not_ recommended, since it can lead to different results on different machines dependent on the computer environment.

- `test`
  - A profile with a complete configuration for automated testing
  - Includes links to test data so needs no other parameters
- `docker`
  - A generic configuration profile to be used with [Docker](https://docker.com/)
- `singularity`
  - A generic configuration profile to be used with [Singularity](https://sylabs.io/docs/)
- `podman`
  - A generic configuration profile to be used with [Podman](https://podman.io/)
- `shifter`
  - A generic configuration profile to be used with [Shifter](https://nersc.gitlab.io/development/shifter/how-to-use/)
- `charliecloud`
  - A generic configuration profile to be used with [Charliecloud](https://charliecloud.io/)
- `apptainer`
  - A generic configuration profile to be used with [Apptainer](https://apptainer.org/)
- `wave`
  - A generic configuration profile to enable [Wave](https://seqera.io/wave/) containers. Use together with one of the above (requires Nextflow ` 24.03.0-edge` or later).
- `conda`
  - A generic configuration profile to be used with [Conda](https://conda.io/docs/). Please only use Conda as a last resort i.e. when it's not possible to run the pipeline with Docker, Singularity, Podman, Shifter, Charliecloud, or Apptainer.

### `-resume`

Specify this when restarting a pipeline. Nextflow will use cached results from any pipeline steps where the inputs are the same, continuing from where it got to previously. For input to be considered the same, not only the names must be identical but the files' contents as well. For more info about this parameter, see [this blog post](https://www.nextflow.io/blog/2019/demystifying-nextflow-resume.html).

You can also supply a run name to resume a specific run: `-resume [run-name]`. Use the `nextflow log` command to show previous run names.

### `-c`

Specify the path to a specific config file (this is a core Nextflow command). See the [nf-core website documentation](https://nf-co.re/usage/configuration) for more information.

## Custom configuration

### Resource requests

Whilst the default requirements set within the pipeline will hopefully work for most people and with most input data, you may find that you want to customise the compute resources that the pipeline requests. Each step in the pipeline has a default set of requirements for number of CPUs, memory and time. For most of the pipeline steps, if the job exits with any of the error codes specified [here](https://github.com/nf-core/rnaseq/blob/4c27ef5610c87db00c3c5a3eed10b1d161abf575/conf/base.config#L18) it will automatically be resubmitted with higher resources request (2 x original, then 3 x original). If it still fails after the third attempt then the pipeline execution is stopped.

To change the resource requests, please see the [max resources](https://nf-co.re/docs/usage/configuration#max-resources) and [tuning workflow resources](https://nf-co.re/docs/usage/configuration#tuning-workflow-resources) section of the nf-core website.

### Custom Containers

In some cases, you may wish to change the container or conda environment used by a pipeline steps for a particular tool. By default, nf-core pipelines use containers and software from the [biocontainers](https://biocontainers.pro/) or [bioconda](https://bioconda.github.io/) projects. However, in some cases the pipeline specified version maybe out of date.

To use a different container from the default container or conda environment specified in a pipeline, please see the [updating tool versions](https://nf-co.re/docs/usage/configuration#updating-tool-versions) section of the nf-core website.

### Custom Tool Arguments

A pipeline might not always support every possible argument or option of a particular tool used in pipeline. Fortunately, nf-core pipelines provide some freedom to users to insert additional parameters that the pipeline does not include by default.

To learn how to provide additional arguments to a particular tool of the pipeline, please see the [customising tool arguments](https://nf-co.re/docs/usage/configuration#customising-tool-arguments) section of the nf-core website.

### nf-core/configs

In most cases, you will only need to create a custom config as a one-off but if you and others within your organisation are likely to be running nf-core pipelines regularly and need to use the same settings regularly it may be a good idea to request that your custom config file is uploaded to the `nf-core/configs` git repository. Before you do this please can you test that the config file works with your pipeline of choice using the `-c` parameter. You can then create a pull request to the `nf-core/configs` repository with the addition of your config file, associated documentation file (see examples in [`nf-core/configs/docs`](https://github.com/nf-core/configs/tree/master/docs)), and amending [`nfcore_custom.config`](https://github.com/nf-core/configs/blob/master/nfcore_custom.config) to include your custom profile.

See the main [Nextflow documentation](https://www.nextflow.io/docs/latest/config.html) for more information about creating your own configuration files.

If you have any questions or issues please send us a message on [Slack](https://nf-co.re/join/slack) on the [`#configs` channel](https://nfcore.slack.com/channels/configs).

## Running in the background

Nextflow handles job submissions and supervises the running jobs. The Nextflow process must run until the pipeline is finished.

The Nextflow `-bg` flag launches Nextflow in the background, detached from your terminal so that the workflow does not stop if you log out of your session. The logs are saved to a file.

Alternatively, you can use `screen` / `tmux` or similar tool to create a detached session which you can log back into at a later time.
Some HPC setups also allow you to run nextflow within a cluster job submitted your job scheduler (from where it submits more jobs).

## Nextflow memory requirements

In some cases, the Nextflow Java virtual machines can start to request a large amount of memory.
We recommend adding the following line to your environment to limit this (typically in `~/.bashrc` or `~./bash_profile`):

```bash
NXF_OPTS='-Xms1g -Xmx4g'
```
