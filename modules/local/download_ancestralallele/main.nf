/*
 * MuSA
 * Module: DOWNLOAD_ANCESTRALALLELE
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_ANCESTRALALLELE {
    tag "vep_setup"    
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"

    output:
    path "AncestralAllele"

    script:
    """
    URL="https://ftp.ensembl.org/pub/current_fasta/ancestral_alleles/homo_sapiens_ancestor_GRCh38.tar.gz"
    OUT=\$(basename "\$URL")

    mkdir -p AncestralAllele
    cd AncestralAllele

    bash download_and_check.sh \$URL 0.1 wget \$OUT

    tar xfz \$OUT
    bgzip -c homo_sapiens_ancestor_GRCh38/*.fa > homo_sapiens_ancestor_GRCh38.fa.gz
    rm -rf homo_sapiens_ancestor_GRCh38/ homo_sapiens_ancestor_GRCh38.tar.gz
    cd ..

    """
}