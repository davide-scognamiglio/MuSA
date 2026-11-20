/*
 * MuSA
 * Module: REPEAT_REGIONS
 * Purpose: The repeat regions a variant overlaps (UCSC RepeatMasker simple, low-complexity and
 *          satellite repeats; Tandem Repeats Finder), from the BED DOWNLOAD_REPEAT_REGIONS installed
 *
 * Adds Repeat_region; see bin/repeat_regions.py. The fact behind the "repeat region" clause of
 * ACMG PM4 and BP3: MuSA reports the overlap, the classifier decides the criterion.
 */

process REPEAT_REGIONS {
    tag "${meta.patient} | repeat regions"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.repeats.maf")

    script:
    """
    repeat_regions.py annotate --maf ${maf} \\
        --bed /data/repeat_regions/repeat_regions.bed.gz \\
        --output ${meta.patient}.repeats.maf
    """
}
