/*
 * MuSA
 * Module: DOWNLOAD_MAXENTSCAN
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_MAXENTSCAN {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "MaxEntScan"

    script:
    """
    mkdir -p MaxEntScan
    cd MaxEntScan

    URL="https://github.com/matthdsm/MaxEntScan/archive/refs/heads/master.zip"
    OUT="fordownload.zip"
    wget \$URL -O \$OUT
    unzip fordownload.zip
    cd ..
    """
}