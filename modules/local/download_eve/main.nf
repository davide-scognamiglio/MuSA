/*
 * MuSA
 * Module: DOWNLOAD_EVE
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_EVE {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "EVE"

    script:
    """
    mkdir -p EVE
    cd EVE

    URL="https://evemodel.org/api/proteins/bulk/download/"
    OUT="download.zip"
    wget \$URL -O \$OUT
    unzip download.zip -d download/
    DATA_FOLDER=download/vcf_files_missense_mutations/
    OUTPUT_NAME=eve_merged.vcf
    cat \$(ls \$DATA_FOLDER/*vcf | head -n1) > header
    ls \$DATA_FOLDER/*vcf | while read VCF; do grep -v '^#' \$VCF >> variants; done
    cat header variants | awk '\$1 ~ /^#/ {print \$0; next} {print \$0 | "sort -k1,1V -k2,2n"}' > \$OUTPUT_NAME
    rm header variants
    bgzip \$OUTPUT_NAME
    tabix \$OUTPUT_NAME.gz
    rm -r download download.zip
    cd ..
    """
}