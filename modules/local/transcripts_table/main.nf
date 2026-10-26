/*
 * MuSA
 * Module: TRANSCRIPTS_TABLE
 * Purpose: <patient>.transcripts.tsv.gz, every transcript of every variant keyed like the MAF,
 *          with the one the MAF reports marked (MuSA_pick). See bin/transcripts_table.py.
 */

process TRANSCRIPTS_TABLE {
    tag "${meta.patient} | transcripts table"
    container "dsbioinfo/musa-helper:rebuild"
    publishDir path: { "${params.outdir}/${params.date}/${meta.patient}" }, mode: "copy"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        tuple val(meta), path(maf), path(vep_vcf)

    output:
        tuple val(meta), path("${meta.patient}.transcripts.tsv.gz")

    script:
        """
        transcripts_table.py --vep ${vep_vcf} --maf ${maf} --output ${meta.patient}.transcripts.tsv.gz
        """
}
