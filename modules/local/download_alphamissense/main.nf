/*
 * MuSA
 * Module: DOWNLOAD_ALPHAMISSENSE
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_ALPHAMISSENSE {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('alphamissense_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_alphamissense" "${changed_entries}" "/data/vep_data/AlphaMissense"; then
        echo "[INFO] No changes for download_alphamissense -- skipping download, reusing existing data."
        cp "${manifest}" alphamissense_manifest.yaml
        exit 0
    fi

    mkdir -p AlphaMissense
    cd AlphaMissense

    # Single entry expected
    prefix="vep_alphamissense"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    # Write SHA back into manifest
    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # Index with tabix
    tabix -s 1 -b 2 -e 2 -f -S 1 "\${!out_var}"

    cd ..

    # Emit updated manifest
    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "AlphaMissense" "/data/vep_data/AlphaMissense"

    mv ${manifest} alphamissense_manifest.yaml
    """
}