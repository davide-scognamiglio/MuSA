/*
 * MuSA
 * Module: DOWNLOAD_PLI
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_PLI {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('pli_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_pli" "${changed_entries}" "/data/vep_data/pLI"; then
        echo "[INFO] No changes for download_pli -- skipping download, reusing existing data."
        cp "${manifest}" pli_manifest.yaml
        exit 0
    fi

    mkdir pLI
    cd pLI

    prefix="vep_pli"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # -------------------------
    # Post-processing
    # -------------------------

    awk '{print \$2, \$20 }' "\${!out_var}" > pli_gene.txt

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "pLI" "/data/vep_data/pLI"

    mv ${manifest} pli_manifest.yaml
    """
}