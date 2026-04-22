/*
 * MuSA
 * Module: DOWNLOAD_PLI
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_PLI {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "pLI"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("pLI"),file('pli_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

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

    mv ${manifest} pli_manifest.yaml
    """
}