/*
 * MuSA
 * Module: DOWNLOAD_MAVEDB
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_MAVEDB {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "MaveDB"

    script:
    """
    mkdir -p MaveDB
    cd MaveDB

    URL="https://ftp.ensembl.org/pub/current_variation/MaveDB/MaveDB_variants.tsv.gz"
    OUT="MaveDB_variants.tsv.gz"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    URL="https://ftp.ensembl.org/pub/current_variation/MaveDB/MaveDB_variants.tsv.gz.tbi"
    OUT="MaveDB_variants.tsv.gz.tbi"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    cd ..
    """
}