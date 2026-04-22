/*
 * MuSA
 * Module: GENEBE_ANNOTATE_VCF
 * Purpose: Annotate variants using GeneBe API
 */


process GENEBE_ANNOTATE_VCF {
    tag "genebe-annotation"
    cpus 1
    errorStrategy 'retry'
    maxRetries 3
    memory { 4.GB * task.attempt }
    container "genebe/pygenebe:0.1.15"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.genebe_annotation.vcf")

    script:
        """
        echo "Running GeneBe annotation..."

        genebe annotate --input $vcf --output ${meta.patient}.genebe_annotation.vcf \\
            --username ${params.gb_user} --api_key ${params.gb_api_key}  \\
            --omit_basic --omit_advanced --omit_csq --omit_ensembl
        """
}