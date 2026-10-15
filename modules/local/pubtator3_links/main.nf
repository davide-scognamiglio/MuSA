/*
 * MuSA
 * Module: PUBTATOR3_LINKS
 * Purpose: PubMed articles that mention the variant (PubTator3 text mining, ClinVar and dbSNP
 *          citations), from the index DOWNLOAD_PUBTATOR3 installed
 *
 * Adds PubTator3_n, PubTator3_pmids (up to 50, ClinVar-cited first, newest first) and
 * PubTator3_source; see bin/pubtator3_links.py. Matched on rsID, gene + protein change and
 * gene + cDNA change.
 */

process PUBTATOR3_LINKS {
    tag "${meta.patient} | PubTator3"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.pubtator3.maf")

    script:
    """
    pubtator3_links.py --maf ${maf} \\
        --index /data/pubtator3/pubtator3_index.tsv.gz \\
        --output ${meta.patient}.pubtator3.maf
    """
}
