/*
 * MuSA
 * Module: DOWNLOAD_DBSCSNV
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_DBSCSNV {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "dbscSNV"

    script:
    """
    mkdir -p dbscSNV
    cd dbscSNV
    URL="https://usf.box.com/shared/static/ffwlywsat3q5ijypvunno3rg6steqfs8"
    OUT="dbscSNV1.1.zip"
    wget \$URL -O \$OUT
    unzip dbscSNV1.1.zip
    head -n1 dbscSNV1.1.chr1 > h
    cat dbscSNV1.1.chr* | grep -v ^chr | sort -k5,5 -k6,6n | cat h - | awk '\$5 != "."' | bgzip -c > dbscSNV1.1_GRCh38.txt.gz
    tabix -s 5 -b 6 -e 6 -c c dbscSNV1.1_GRCh38.txt.gz
    cd ..
    """
}