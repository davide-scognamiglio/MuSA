/*
 * MuSA
 * Module: DOWNLOAD_SPLICEVAULT
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_SPLICEVAULT {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "SpliceVault"

    script:
    """
    mkdir -p SpliceVault
    cd SpliceVault

    URL="https://ftp.ensembl.org/pub/current_variation/SpliceVault/SpliceVault_data_GRCh38.tsv.gz"
    OUT="SpliceVault_data_GRCh38.tsv.gz"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    URL="https://ftp.ensembl.org/pub/current_variation/SpliceVault/SpliceVault_data_GRCh38.tsv.gz.tbi"
    OUT="SpliceVault_data_GRCh38.tsv.gz.tbi"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    cd ..
    """
}