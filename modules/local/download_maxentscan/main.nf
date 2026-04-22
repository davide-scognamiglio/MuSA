/*
 * MuSA
 * Module: DOWNLOAD_MAXENTSCAN
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_MAXENTSCAN {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "MaxEntScan"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("MaxEntScan"),file('maxentscan_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p MaxEntScan
    cd MaxEntScan

    prefix="vep_maxentscan"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # -------------------------
    # Unpack
    # -------------------------

    unzip "\${!out_var}"
    rm -f "\${!out_var}"

    cd ..

    mv ${manifest} maxentscan_manifest.yaml
    """
}