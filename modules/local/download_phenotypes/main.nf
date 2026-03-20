/*
 * MuSA
 * Module: DOWNLOAD_PHENOTYPES
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_PHENOTYPES {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "Phenotypes"

    script:
    """
    mkdir -p Phenotypes
    """
}