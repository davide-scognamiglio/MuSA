/*
 * MuSA
 * Module: DOWNLOAD_GWAS
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_GWAS {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "GWAS"

    script:
    """
    mkdir -p GWAS
    cd GWAS

    URL="https://www.ebi.ac.uk/gwas/api/search/downloads/associations/v1.0?split=false"
    OUT="gwas.zip"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    unzip gwas.zip
    rm gwas.zip 
    cd ..
    """
}