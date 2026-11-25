/*
 * MuSA
 * Module: HPO_RESOLVE
 * Purpose: Turn every patient's samplesheet HPO terms (codes or exact primary names, any case)
 *          into current HPO codes, once per run and before any annotation, so a typo or a synonym
 *          stops the run in seconds instead of after VEP. See bin/hpo_match.py --resolve.
 */

process HPO_RESOLVE {
    tag "samplesheet HPO terms"
    container "dsbioinfo/musa-helper:rebuild"
    memory "2 GB"

    input:
        path(terms)    // patient<TAB>raw terms, one line per samplesheet row

    output:
        path("hpo_resolved.tsv")

    script:
        """
        hpo_match.py --resolve ${terms} --hpo-dir /data/hpo --output hpo_resolved.tsv
        """
}
