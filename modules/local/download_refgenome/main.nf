/*
 * MuSA
 * Module: DOWNLOAD_REFGENOME
 * Purpose: Download/create reference genome files
 */


process DOWNLOAD_REFGENOME{
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/gatk:latest"

    output:
    path "reference_genome"

    script:
    """
    echo ${params.http_proxy}
    mkdir reference_genome
    cd reference_genome

    URL="https://hgdownload.soe.ucsc.edu/goldenpath/${params.build}/bigZips/${params.build}.fa.gz"
    OUT="${params.build}.fa.gz"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    # Create .dict using GATK (Picard)
    gunzip ${params.build}.fa.gz

    samtools faidx ${params.build}.fa

    gatk CreateSequenceDictionary \
        -R ${params.build}.fa \
        -O ${params.build}.dict

    cd ..
    """
}