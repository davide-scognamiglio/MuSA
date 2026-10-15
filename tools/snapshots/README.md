# MuSA annotation snapshots

Two sources MuSA reads have no versioned download upstream:

- **MaveDB** is an API. Its bulk mapped data cannot be fetched per user: data downloads are limited to
  100 requests per IP per 300 s.
- **PubTator3**'s `mutation2pubtator3.gz` is replaced in place by NCBI, with no archive.

So once per MuSA release a maintainer builds dated snapshots of both and publishes them in MuSA's
Zenodo record "MuSA annotation snapshots". `dbs_manifest.yaml` pins each file by URL and SHA-256, like
every other source. Users only download; they never call these scripts.

## Build

Inputs: the MANE summary (`MANE.GRCh38.v<version>.summary.txt.gz`, NCBI) and PubTator3's current
`mutation2pubtator3.gz`.

    # MaveDB: hours; resumable, rerun to retry what failed
    tools/snapshots/mavedb_snapshot.py fetch --cache mavedb_cache
    tools/snapshots/mavedb_snapshot.py build --cache mavedb_cache \
        --mane MANE.GRCh38.v1.5.summary.txt.gz --out snapshot --date 2026-10-15

    # PubTator3: about a minute
    tools/snapshots/pubtator3_snapshot.py mutation2pubtator3.gz MANE.GRCh38.v1.5.summary.txt.gz \
        snapshot 2026-10-15

`snapshot/` then holds:

| file | what | licence |
|---|---|---|
| `mavedb_cc0_by.tsv.gz` | MaveDB score sets under CC0 or CC BY 4.0 | CC BY 4.0 (CC0 sets need no attribution; the CC BY ones are listed in `ATTRIBUTION.tsv`) |
| `mavedb_by_sa.tsv.gz` | score sets under CC BY-SA 4.0 | CC BY-SA 4.0 |
| `mavedb_by_nc_sa.tsv.gz` | score sets under CC BY-NC-SA 4.0 | CC BY-NC-SA 4.0 (non-commercial) |
| `ATTRIBUTION.tsv` | every score set: URN, licence, title, target, publication, link | |
| `pubtator3_index.tsv.gz` | the variant → PMID index MuSA reads | public domain (NCBI) |
| `mutation2pubtator3_<date>.gz` | NCBI's file as downloaded, for provenance | public domain (NCBI) |
| `SOURCES*.txt`, `SHA256SUMS*` | provenance and checksums | |

## Publish

1. Upload `snapshot/` as a new version of the Zenodo record. Its description lists the files above,
   with their licences, the MaveDB and PubTator3 citations, and the MuSA release they belong to.
2. Put each file's Zenodo download URL and SHA-256 into the `mavedb_*` and `pubtator3_index` entries
   of test-datasets' `dbs_manifest.yaml`, and set `version` to the snapshot date.
3. Run `setup --update_db_only true` against the new manifest, then the release checks.
