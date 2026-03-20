/*
 * MuSA
 * Module: ADD_GENOME_CHANGE
 * Purpose: Add genome-level change information to a MAF file
 */


process ADD_GENOME_CHANGE {
    tag "add-genome-change"
    cpus 1
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container 'dsbioinfo/musa-helper:latest'

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.with_genome_change.maf")

    script:
        """
        getGenomeChange.sh ${maf} ${meta.patient}.with_genome_change.maf
        """
}