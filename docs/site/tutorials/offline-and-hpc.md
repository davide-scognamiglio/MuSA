---
title: Offline, HPC and air-gapped installs
summary: Singularity on a cluster, proxies, and annotating on a machine with no network.
order: 3
---

# Offline, HPC and air-gapped installs

Hospital and cluster machines often have no Docker, a proxy, or no network at all. MuSA is built
for that: only `setup` downloads, and `annotate` runs offline by default.

## Singularity or Apptainer instead of Docker

Swap the profile. Everything else stays the same.

```bash
nextflow run davide-scognamiglio/MuSA --workflow setup \
  --data_dir /shared/musa_data -profile singularity

nextflow run davide-scognamiglio/MuSA --workflow annotate \
  --input samplesheet.csv --outdir results \
  --data_dir /shared/musa_data -profile singularity
```

Podman works the same way with `-profile podman`.

## Running on a cluster scheduler

Tell Nextflow about your scheduler in a small config file, for example for SLURM:

```groovy
// cluster.config
process {
    executor = 'slurm'
    queue    = 'your_queue'
}
```

```bash
nextflow run davide-scognamiglio/MuSA ... -profile singularity -c cluster.config
```

Put `--data_dir` on a filesystem every compute node can see, and keep it an absolute path. The
[Usage](../../docs/usage/) page covers resource requests and custom configuration.

## Behind a proxy

`setup` needs to reach the database providers. Pass your proxy to the containers:

```bash
nextflow run davide-scognamiglio/MuSA --workflow setup \
  --data_dir $PWD/musa_data -profile docker \
  --http_proxy http://proxy.example.org:8080 \
  --https_proxy http://proxy.example.org:8080
```

Nextflow itself also needs to download the pipeline: export `http_proxy` and `https_proxy` in your
shell before running it.

## Air-gapped: set up on one machine, annotate on another

1. On a machine with network access, run `setup` as usual.
2. Pull the pipeline and its containers there too, and copy them across with the data:
   `nextflow pull davide-scognamiglio/MuSA -r v1.4.0` puts the code in `~/.nextflow/assets/`;
   with Singularity, set `NXF_SINGULARITY_CACHEDIR` so the images land in one folder you can copy.
3. Copy the database directory, `~/.nextflow/assets/davide-scognamiglio/MuSA` and the image
   folder to the offline machine, keeping the database directory's absolute path if you can.
4. Run `annotate` there with `-offline` (Nextflow's own flag: don't check for updates) and the same
   `-r` version.

`annotate` makes no network calls in its default offline mode. The one exception is optional:
`--offline false` sends variants to the GeneBe API for ACMG/AMP scoring.

## What leaves the machine

| Step | Network | What is sent |
|---|---|---|
| `setup` | Yes | Download requests to the database providers. No patient data. |
| `annotate` (default) | No | Nothing |
| `annotate --offline false` | Yes | Variants to the GeneBe API, for ACMG/AMP scoring |
