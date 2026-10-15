/*
 * MuSA
 * Module: DOWNLOAD_PUBTATOR3
 * Purpose: PubTator3 variant -> PubMed index, for the PubTator3_* columns
 *
 * Downloads NCBI's mutation2pubtator3.gz (~116 MB) and the MANE summary (NCBI Gene id -> symbol)
 * and builds the index PUBTATOR3_LINKS reads (~28 MB, ~40 s, ~2.5 GB RAM; see
 * bin/pubtator3_links.py). NCBI replaces mutation2pubtator3.gz in place and keeps no older
 * versions, so a newer file than the manifest's is expected: its checksum is recorded and shown as
 * MISMATCH in the setup report, and setup carries on. The raw file is deleted once indexed.
 */


process DOWNLOAD_PUBTATOR3 {
    tag "pubtator3_setup"
    container "dsbioinfo/musa-helper:rebuild"
    memory { 4.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

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

    if should_skip_module "pubtator3 mane_summary" "${changed_entries}" "/data/pubtator3"; then
        echo "[INFO] No changes for download_pubtator3 -- skipping download, reusing existing data."
        cp "${manifest}" pubtator3_manifest.yaml
        exit 0
    fi

    mkdir -p pubtator3
    cd pubtator3
    # Hashed and recorded, not enforced: see the header for why a mismatch is expected here.
    for key in pubtator3 mane_summary; do
        url_var="\${key}_url"; method_var="\${key}_method"; out_var="\${key}_out"
        sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")
        write_computed_sha256 "\$PWD/../${manifest}" "\$key" "\$sha"
    done
    pubtator3_links.py build "\${pubtator3_out}" "\${mane_summary_out}" pubtator3_index.tsv.gz
    rm "\${pubtator3_out}"
    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "pubtator3" "/data/pubtator3"

    mv ${manifest} pubtator3_manifest.yaml
    """
}
