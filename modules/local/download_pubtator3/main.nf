/*
 * MuSA
 * Module: DOWNLOAD_PUBTATOR3
 * Purpose: PubTator3 variant -> PubMed index, for the PubTator3_* columns
 *
 * NCBI publishes mutation2pubtator3 without keeping older versions, so MuSA reads a dated snapshot
 * of it from its own Zenodo record: the original file archived as is, and the index
 * tools/snapshots/pubtator3_snapshot.py built from it (~28 MB). Only the index is downloaded.
 */


process DOWNLOAD_PUBTATOR3 {
    tag "pubtator3_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('pubtator3_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "pubtator3_index" "${changed_entries}" "/data/pubtator3"; then
        echo "[INFO] No changes for download_pubtator3 -- skipping download, reusing existing data."
        cp "${manifest}" pubtator3_manifest.yaml
        exit 0
    fi

    mkdir -p pubtator3
    cd pubtator3
    fetch_entry "\$PWD/../${manifest}" pubtator3_index
    [ "\${pubtator3_index_out}" = pubtator3_index.tsv.gz ] || mv "\${pubtator3_index_out}" pubtator3_index.tsv.gz
    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "pubtator3" "/data/pubtator3"

    mv ${manifest} pubtator3_manifest.yaml
    """
}
