/*
 * MuSA
 * Module: DOWNLOAD_PLI
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_PLI {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "pLI"

    script:
    """
    mkdir pLI
    cd pLI
    
    URL="https://raw.githubusercontent.com/Ensembl/VEP_plugins/release/112/pLI_values.txt"
    OUT="pLI_values.txt"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    awk '{print \$2, \$20 }'  pLI_values.txt > plI_gene.txt 
    cd ..
    """
}