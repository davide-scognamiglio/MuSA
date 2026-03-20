/*
 * MuSA
 * Module: DOWNLOAD_ENFORMER
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_ENFORMER {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "Enformer"

    script:
    """
    mkdir -p Enformer

    URL="https://ftp.ensembl.org/pub/current_variation/Enformer/enformer_grch38.vcf.gz"
    OUT="enformer_grch38.vcf.gz"
    bash download_and_check.sh \$URL 0.1 wget \$OUT
    
    URL="https://ftp.ensembl.org/pub/current_variation/Enformer/enformer_grch38.vcf.gz.tbi"
    OUT="enformer_grch38.vcf.gz.tbi"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    """
}