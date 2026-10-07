---
title: Your first MuSA run
summary: Install, build the database directory, run the test, then annotate your own VCF.
order: 1
---

# Your first MuSA run

This walkthrough takes you from nothing to a report for your own VCF, in basic mode. Basic mode
needs no registration and no network once its databases are downloaded.

**You need:** Linux or macOS, Java 17 or later (for Nextflow), Docker, Singularity/Apptainer or
Podman, and about 30 GB of disk for the database directory.

## 1. Install Nextflow

MuSA needs Nextflow 25.10.0 or later.

```bash
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/    # or anywhere on your PATH
nextflow -version
```

Already have it? Run `nextflow self-update` if it's older than 25.10.0.

## 2. Build the database directory

Once per machine. This downloads basic mode: Ensembl VEP's cache, the reference genome, ClinVar,
ClinGen and the Human Phenotype Ontology, about 30 GB.

```bash
nextflow run davide-scognamiglio/MuSA \
  --workflow setup \
  --data_dir $PWD/musa_data \
  -profile docker
```

- `--data_dir` **must be an absolute path.** The container engine mounts it as given, and MuSA
  stops at start-up if it's relative. `$PWD/musa_data` is fine; `musa_data` is not.
- Use the same path for `setup` and every later `annotate`.
- When it finishes, `musa_data/setup_report.html` lists every file that landed, its version and
  its SHA-256 checksum.

Behind a proxy? Add `--http_proxy http://host:port --https_proxy http://host:port`. See
[Offline, HPC and air-gapped installs](../offline-and-hpc/).

## 3. Run the bundled test

A single-variant VCF that proves the containers and the database directory are wired correctly.
It takes a couple of minutes.

```bash
nextflow run davide-scognamiglio/MuSA \
  -profile test,docker \
  --data_dir $PWD/musa_data \
  --outdir output_test
```

Open `output_test/<date>/NA12877/NA12877_maf_dashboard.html` in a browser.

## 4. Annotate your own VCF

Write a samplesheet, one row per patient. The `hpo` column is optional: give the patient's HPO
terms, separated by `;`, and MuSA matches every gene against them, offline.

```csv
patient,sample_type,sample_file,hpo
PATIENT_01,blood,/path/to/PATIENT_01.vcf.gz,HP:0001250;HP:0002121
PATIENT_02,saliva,/path/to/PATIENT_02.vcf.gz,
```

Then run:

```bash
nextflow run davide-scognamiglio/MuSA \
  --workflow annotate \
  --input samplesheet.csv \
  --outdir results \
  --data_dir $PWD/musa_data \
  -profile docker
```

VCFs from nf-core/sarek: add `--vcf_format sarek` so its hard-filter conventions are applied.
Input must be GRCh38. MuSA stops rather than mis-annotate a GRCh37 VCF.

## 5. What you get

```
results/<date>/PATIENT_01/
├── PATIENT_01_maf_dashboard.html   the report: open it in any browser, no server
├── PATIENT_01.filtered.maf         the variants worth reviewing
└── PATIENT_01.raw.maf              every variant, every column
```

- **The report** starts with the review set, then groups findings by why they matter: ClinVar
  pathogenic, loss of function in an established disease gene, biallelic, fits the patient's
  phenotype. See [an example](../../example/).
- **The MAF** has one row per variant and one transcript per variant (MANE Select). Column
  reference: [Output](../../docs/output/). To analyse it, see
  [The MAF in Python](../maf-in-python/).

## Next

- **Pin a version** for reproducible runs: `-r v1.4.0`.
- **Extended mode** (dbNSFP, 32 VEP plugins, RENOVO 1.5, ~200 GB): run `setup` again with
  `--extended true` and your dbNSFP download, then `annotate --extended true`. Details in
  [Usage](../../docs/usage/).
