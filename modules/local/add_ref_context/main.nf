/*
 * MuSA
 * Module: ADD_REF_CONTEXT
 * Purpose: Add reference genome context around variants in a MAF
 */


process ADD_REF_CONTEXT {
    tag "add-ref-context"
    cpus 1
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container 'dsbioinfo/musa-helper:latest'

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.raw.maf")

    script:
        """
        getRefContext.py \
            --input ${maf} \
            --output ${meta.patient}.raw.maf \
            --fasta "/data/vep_data/reference_genome/${params.build}.fa" \
            --window 10 \
            --chrom_col "Chromosome" \
            --pos_col "Start_Position"
        """
}

