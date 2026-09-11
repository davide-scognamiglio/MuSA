/*
 * nf-core/variantannotation
 * Module: GATHER_DBNSFP_TSV
 * Purpose: Concatenate per-chromosome dbNSFP shards back into one TSV per patient
 */

process GATHER_DBNSFP_TSV {
    tag "gather-dbNSFP-${meta.patient}"
    cpus 1
    memory "2 GB"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), path(tsvs)

    output:
        tuple val(meta), path("${meta.patient}.dbnsfp.tsv")

    script:
    """
    out="${meta.patient}.dbnsfp.tsv"
    : > "\$out"
    header_written=0

    for f in ${tsvs}; do
        [ -s "\$f" ] || continue
        if [ "\$header_written" -eq 0 ]; then
            cat "\$f" >> "\$out"
            header_written=1
        else
            tail -n +2 "\$f" >> "\$out"
        fi
    done
    """
}
