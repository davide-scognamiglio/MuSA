/*
 * MuSA
 * Module: DOWNLOAD_CADD
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_CADD {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "CADD"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path('CADD'),file('cadd_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p CADD
    cd CADD

    # Loop over CADD entries defined in manifest
    for var in \$(compgen -v); do
        if [[ \$var =~ ^vep_cadd_.*_url\$ ]]; then
            prefix="\${var%_url}"

            method_var="\${prefix}_method"
            out_var="\${prefix}_out"

            echo "[INFO] Processing \$prefix"

            sha=\$(download_and_compute_sha "\${!var}" "\${!method_var}" "\${!out_var}")

            # Write SHA back into manifest
            write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

            echo "[INFO] \$prefix hash written"
        fi
    done

    cd ..

    # Rename manifest for downstream consistency
    mv ${manifest} cadd_manifest.yaml
    """
}