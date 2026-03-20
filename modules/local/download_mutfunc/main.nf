/*
 * MuSA
 * Module: DOWNLOAD_MUTFUNC
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_MUTFUNC {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "mutfunc"

    script:
    """
    mkdir -p mutfunc
    cd mutfunc

    URL="https://ftp.ensembl.org/pub/current_variation/mutfunc/mutfunc_data.db"
    OUT="mutfunc_data.db"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    cd ..
    """
}