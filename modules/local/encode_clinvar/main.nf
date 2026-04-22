/*
 * MuSA
 * Module: ENCODE_CLINVAR
 * Purpose: Encode comma-delimited values of clinvar into one single value.
 */


process ENCODE_CLINVAR {
    tag "encode-clinvar"
    cpus 1
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container 'dsbioinfo/musa-helper:rebuild'

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.clinvar_encoded.maf")

    script:
    """
    encode_clinvar.py \\
        --file    ${maf} \\
        --sig_col clinvar_clnsig \\
        --rev_col clinvar_review \\
        --output  "${meta.patient}.clinvar_encoded.maf"
    """
}