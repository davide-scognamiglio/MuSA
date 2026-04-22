/*
 * MuSA
 * Module: DOWNLOAD_ANNOVAR_DB
 * Purpose: Download ANNOVAR databases
 */


 process DOWNLOAD_ANNOVAR_DB {
    tag "renovo_setup"
    publishDir "${params.data_dir}", mode: 'copy', overwrite: true, pattern: "renovo_humandb"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path('renovo_humandb'),file('annovar_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p renovo_humandb
    cd renovo_humandb

    # Loop over matching variables
    for var in \$(compgen -v); do
        if [[ \$var =~ ^annovar_.*_url\$ ]]; then
            prefix="\${var%_url}"

            method_var="\${prefix}_method"
            out_var="\${prefix}_out"

            sha=\$(download_and_compute_sha "\${!var}" "\${!method_var}" "\${!out_var}")
            write_computed_sha256 "../${manifest}" "\$prefix" \$sha
            echo "\$prefix hash written in file!"
        fi
    done


    gunzip -f *.gz
    cd ..
    mv ${manifest} annovar_manifest.yaml
    """
}
