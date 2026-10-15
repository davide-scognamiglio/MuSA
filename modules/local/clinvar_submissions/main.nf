/*
 * MuSA
 * Module: CLINVAR_SUBMISSIONS
 * Purpose: What ClinVar submitters wrote about the variant, as facts
 *
 * Adds the ClinVar_SCV_* columns (how many submissions name PS3 or BS3, describe a functional study
 * and with what result, or state that none exists; the cited PMIDs and the shortest such sentence)
 * and ClinVar_EP_codes (the expert panel's own classification and codes, kept apart so a benchmark
 * can leave them out), from the index DOWNLOAD_CLINVAR_SUBMISSIONS built; see
 * bin/clinvar_submissions.py. Joined on ClinVar_VariationID.
 */

process CLINVAR_SUBMISSIONS {
    tag "${meta.patient} | ClinVar submissions"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${maf.baseName}.submissions.maf")

    script:
    """
    clinvar_submissions.py annotate --maf ${maf} \\
        --index /data/clinvar_submissions/clinvar_submissions.tsv.gz \\
        --output ${maf.baseName}.submissions.maf
    """
}
