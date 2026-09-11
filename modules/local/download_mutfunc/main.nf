/*
 * MuSA
 * Module: DOWNLOAD_MUTFUNC
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_MUTFUNC {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "mutfunc"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('mutfunc_manifest.yaml')
        
    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_mutfunc" "${changed_entries}" "/data/vep_data/mutfunc"; then
        echo "[INFO] No changes for download_mutfunc -- skipping download, reusing existing data."
        cp "${manifest}" mutfunc_manifest.yaml
        exit 0
    fi

    mkdir -p mutfunc
    cd mutfunc

    prefix="vep_mutfunc"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    cd ..

    mv ${manifest} mutfunc_manifest.yaml
    """
}