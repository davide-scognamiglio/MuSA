/*
 * MuSA
 * Module: RENOVO_SCORE
 * Purpose: Add RENOVO's pathogenicity score and class to the merged annotations
 *
 * renovo-rebuild (https://github.com/davide-scognamiglio/renovo-rebuild) runs RENOVO's published random
 * forest on columns MuSA has already annotated: VEP consequence and gnomAD 4.1 AF, dbNSFP 5 scores and
 * MuSA's ClinVar. It replaces the RENOVO branch that re-annotated every VCF with ANNOVAR. See the
 * renovo-rebuild README for the input substitutions and their measured effect on scores.
 */

process RENOVO_SCORE {
    tag "renovo-score"
    // Measured on exomes and 50,000-variant ClinVar chunks: 3-8 s and ~0.45 GB. Reading the table is the
    // only multithreaded step and gains nothing beyond 4 threads.
    cpus 4
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container params.renovo_container

    input:
        tuple val(meta), file(merged)

    output:
        tuple val(meta), file("${meta.patient}.merged_renovo.tsv")

    script:
        """
        set -euo pipefail

        renovo-rebuild score --table "${merged}" --map musa --output renovo.tsv --threads ${task.cpus}

        # renovo-rebuild writes one row per input row, in input order, so its two score columns can be
        # pasted on instead of joined. Check that before trusting it: same row count, same variant keys
        # (CHROM POS REF ALT are columns 1, 2, 4 and 5 of the merged table, 1-4 of renovo.tsv).
        if ! cmp -s <(cut -f1,2,4,5 "${merged}") <(cut -f1-4 renovo.tsv); then
            echo "RENOVO_SCORE: renovo-rebuild output is not aligned with ${merged}" >&2
            exit 1
        fi

        paste "${merged}" <(cut -f5,6 renovo.tsv) > "${meta.patient}.merged_renovo.tsv"
        """
}
