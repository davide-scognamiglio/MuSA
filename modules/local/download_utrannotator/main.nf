/*
 * MuSA
 * Module: DOWNLOAD_UTRANNOTATOR
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_UTRANNOTATOR {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "UTRannotator"

    script:
    """
    mkdir -p UTRannotator
    cd UTRannotator

    URL="https://raw.githubusercontent.com/Ensembl/UTRannotator/master/uORF_5UTR_GRCh38_PUBLIC.txt"
    OUT="uORF_5UTR_GRCh38_PUBLIC.txt"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    cd ..
    """
}