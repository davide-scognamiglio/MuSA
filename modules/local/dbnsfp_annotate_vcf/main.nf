/*
 * nf-core/variantannotation
 * Module: DBNSFP_ANNOTATE_VCF
 * Purpose: Annotate variants using dbNSFP
 */

process DBNSFP_ANNOTATE_VCF {
    tag "dbNSFP-annotation"
    cpus 1
    errorStrategy 'retry'
    maxRetries 3
    memory { 16.GB * task.attempt }
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.dbnsfp.tsv")

    script:
    """
    jar=\$(find /data/dbNSFP/dbNSFP -maxdepth 1 -name "*.jar" | head -1)
    jar_name=\$(basename "\$jar" .jar)

    java -cp /data/dbNSFP/dbNSFP "\$jar_name" \
        -i ${vcf} \
        -o ${meta.patient}.dbnsfp.tsv \
        -p
    """
}