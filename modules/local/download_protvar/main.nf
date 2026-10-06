/*
 * MuSA
 * Module: DOWNLOAD_PROTVAR
 * Purpose: ProtVar structural context for missense variants (VEP plugin ProtVar)
 *
 * SQLite database: predicted stability change (ddG), overlapping AlphaFold pockets and
 * protein-protein interfaces.
 */


process DOWNLOAD_PROTVAR {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('protvar_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_protvar" "${changed_entries}" "/data/vep_data/ProtVar"; then
        echo "[INFO] No changes for download_protvar -- skipping download, reusing existing data."
        cp "${manifest}" protvar_manifest.yaml
        exit 0
    fi

    mkdir -p ProtVar
    cd ProtVar

    for key in vep_protvar; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "ProtVar" "/data/vep_data/ProtVar"

    mv ${manifest} protvar_manifest.yaml
    """
}
