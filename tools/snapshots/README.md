# MuSA annotation snapshots

PubTator3's `mutation2pubtator3.gz` is replaced in place by NCBI, with no archive of older versions.
So once per MuSA release a maintainer builds a dated snapshot of it and publishes it in MuSA's
Zenodo record "MuSA annotation snapshots". `dbs_manifest.yaml` pins the file by URL and SHA-256,
like every other source. Users only download it; they never run this script.

## Build

Inputs: the MANE summary (`MANE.GRCh38.v<version>.summary.txt.gz`, NCBI), which maps PubTator3's
NCBI Gene ids to the gene symbols MuSA writes, and PubTator3's current `mutation2pubtator3.gz`.

    tools/snapshots/pubtator3_snapshot.py mutation2pubtator3.gz MANE.GRCh38.v1.5.summary.txt.gz \
        snapshot 2026-10-15

It takes about a minute. `snapshot/` then holds:

| file | what | licence |
|---|---|---|
| `pubtator3_index.tsv.gz` | the variant → PMID index MuSA reads | public domain (NCBI) |
| `mutation2pubtator3_<date>.gz` | NCBI's file as downloaded, for provenance | public domain (NCBI) |
| `SOURCES_pubtator3.txt`, `SHA256SUMS_pubtator3` | provenance and checksums | |

## Publish

1. Upload `snapshot/` as a new version of the Zenodo record. Its description lists the files, the
   PubTator3 citation, and the MuSA release they belong to.
2. Put the index's Zenodo download URL and SHA-256 into the `pubtator3_index` entry of
   test-datasets' `dbs_manifest.yaml`, and set `version` to the snapshot date.
3. Run `setup --update_db_only true` against the new manifest, then the release checks.
