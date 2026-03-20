/*
 * MuSA
 * Module: DOWNLOAD_PHENOTYPEORTHOLOGOUS
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_PHENOTYPEORTHOLOGOUS {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "PhenotypeOrthologous"

    script:
    """
    mkdir -p PhenotypeOrthologous
    cd PhenotypeOrthologous

    URL="https://ftp.ensembl.org/pub/current_variation/PhenotypeOrthologous/PhenotypesOrthologous_homo_sapiens_112_GRCh38.gff3.gz"
    OUT="PhenotypesOrthologous_homo_sapiens_112_GRCh38.gff3.gz"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    URL="https://ftp.ensembl.org/pub/current_variation/PhenotypeOrthologous/PhenotypesOrthologous_homo_sapiens_112_GRCh38.gff3.gz.tbi"
    OUT="PhenotypesOrthologous_homo_sapiens_112_GRCh38.gff3.gz.tbi"
    bash download_and_check.sh \$URL 0.1 wget \$OUT

    cd ..
    """
}