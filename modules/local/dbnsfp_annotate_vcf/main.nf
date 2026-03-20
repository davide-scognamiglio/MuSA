/*
 * nf-core/variantannotation
 * Module: VEP_ANNOTATE_VCF
 * Purpose: Annotate variants using Ensembl VEP, optionally with plugins
 */


process DBNSFP_ANNOTATE_VCF {
    tag "dbNSFP-annotation"
    cpus params.n_core
    errorStrategy 'retry'
    maxRetries 3
    memory { 16.GB * task.attempt }
    container "dsbioinfo/musa-helper:latest"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.dbnsfp.tsv")

script:
"""
    ls -lah

    java -cp /data/dbNSFP/dbNSFP5.3.1a search_dbNSFP531a \
        -i ${vcf} \
        -o ${meta.patient}.dbnsfp.tsv \
        -p
    """
}