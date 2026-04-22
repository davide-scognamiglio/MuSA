/*
 * MuSA
 * Module: DOWNLOAD_UTRANNOTATOR
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_UTRANNOTATOR {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "UTRannotator"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("UTRannotator"),file('utrannotator_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p UTRannotator
    cd UTRannotator

    prefix="vep_utrannotator"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    cd ..

    mv ${manifest} utrannotator_manifest.yaml
    """
}