/*
 * MuSA
 * Module: DOWNLOAD_G2P
 * Purpose: Gene2Phenotype panels (VEP plugin G2P)
 *
 * All G2P panels in one CSV. The plugin flags variants whose zygosity and frequency fit the
 * gene's allelic requirement. G2P publishes only its current state, so the manifest pins no
 * checksum.
 */


process DOWNLOAD_G2P {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('g2p_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_g2p" "${changed_entries}" "/data/vep_data/G2P"; then
        echo "[INFO] No changes for download_g2p -- skipping download, reusing existing data."
        cp "${manifest}" g2p_manifest.yaml
        exit 0
    fi

    mkdir -p G2P
    cd G2P

    for key in vep_g2p; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "G2P" "/data/vep_data/G2P"

    mv ${manifest} g2p_manifest.yaml
    """
}
