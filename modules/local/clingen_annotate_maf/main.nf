/*
 * MuSA
 * Module: CLINGEN_ANNOTATE_MAF
 * Purpose: Gene-level ClinGen annotation of the MAF (join by Hugo_Symbol).
 *          Overwrites the authoritative HI columns and adds Triplosensitivity,
 *          Gene-Disease Validity, and Clinical Actionability (Adult/Pediatric).
 *          Variant-level ClinGen (Variant Pathogenicity) is handled separately
 *          via VEP --custom (see VEP_ANNOTATE_VCF).
 */


process CLINGEN_ANNOTATE_MAF {
    tag "clingen-annotate"
    cpus params.n_core
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container 'dsbioinfo/musa-helper:rebuild'

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.clingen.maf")

    script:
        """
        clingen_annotate_maf.py \\
            --input ${maf} \\
            --output ${meta.patient}.clingen.maf \\
            --dosage "/data/clingen/clingen_gene_dosage.tsv" \\
            --gene-disease "/data/clingen/clingen_gene_validity.csv" \\
            --actionability-adult "/data/clingen/clingen_actionability_adult.tsv" \\
            --actionability-pediatric "/data/clingen/clingen_actionability_pediatric.tsv" \\
            --gene-col "Hugo_Symbol"
        """
}
