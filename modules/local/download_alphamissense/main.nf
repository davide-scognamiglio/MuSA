/*
 * MuSA
 * Module: DOWNLOAD_ALPHAMISSENSE
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_ALPHAMISSENSE {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"

    output:
    path "AlphaMissense"

    script:
    """
    URL="https://storage.googleapis.com/dm_alphamissense/AlphaMissense_${params.build}.tsv.gz"
    OUT=\$(basename "\$URL")

    mkdir -p AlphaMissense
    cd AlphaMissense

    bash download_and_check.sh \$URL 0.1 wget \$OUT

    tabix -s 1 -b 2 -e 2 -f -S 1 "\$OUT"

    cd ..
    """
}
