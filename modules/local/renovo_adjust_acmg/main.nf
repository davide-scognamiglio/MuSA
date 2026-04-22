/*
 * MuSA
 * Module: RENOVO_ADJUST_ACMG
 * Purpose: Use Renovo to adjust the acmg score provided by GeneBe
 */

process RENOVO_ADJUST_ACMG {
    tag "renovo-adjust"
    cpus 1
    memory { 18.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${maf.baseName}.renovo_adj.maf")

    script:
    """
    renovo_adjust_acmg.py \\
        --file        ${maf} \\
        --variant_col Variant_Classification \\
        --acmg_col    acmg_score \\
        --pl_col      PL_score \\
        --output      "${maf.baseName}.renovo_adj.maf"
    """
}