/*
 * MuSA
 * Module: HPO_MATCH
 * Purpose: Compare the patient's HPO terms (samplesheet `hpo` column) with each variant's gene,
 *          using the HPO release installed by setup (hp.obo + gene and disease annotations).
 *
 * Adds HPO_match, HPO_match_score, HPO_matched_terms, HPO_best_disease and HPO_panel; see
 * bin/hpo_match.py. FILTER_VARIANTS reads HPO_panel, so phenotype filtering needs no network.
 */

process HPO_MATCH {
    tag "${meta.patient} | HPO ${meta.hpo ? meta.hpo.tokenize(';').size() + ' term(s)' : 'none'}"
    container "dsbioinfo/musa-helper:rebuild"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        tuple val(meta), path(maf)

    output:
        tuple val(meta), path("${meta.patient}.hpo.maf")

    script:
        """
        hpo_match.py \\
            --maf ${maf} \\
            --hpo "${meta.hpo ?: ''}" \\
            --hpo-dir /data/hpo \\
            --output ${meta.patient}.hpo.maf
        """
}
