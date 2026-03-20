/*
 * MuSA
 * Module: DOWNLOAD_CADD
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_CADD {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"

    output:
    path "CADD"

    script:
    """
    mkdir CADD
    cd CADD
    URL="https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz"
    OUT=\$(basename "\$URL")
    bash download_and_check.sh https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz 0.1 wget \$OUT

    URL="https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz.tbi"
    OUT=\$(basename "\$URL")
    bash download_and_check.sh https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz.tbi 0.1 wget \$OUT
    
    cd ..
    """
}