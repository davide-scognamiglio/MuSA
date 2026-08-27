/*
 * MuSA
 * Module: GEN_DBNSFP_ALIGNED_COLUMNS
 * Purpose: Regenerate dbnsfp_transcript_aligned_columns.txt from a fresh dbNSFP install
 *
 * Runs bin/gen_dbnsfp_aligned_columns.py against the freshly-downloaded readme plus the annotated
 * probe panel (assets/dbnsfp_probe_variants.vcf, six real multi-transcript positions run through
 * dbNSFP by the caller subworkflow), instead of requiring a real patient MAF the way the manual
 * workflow does. There is no MAF at DOWNLOAD_DBNSFP time - this is what stands in for one.
 *
 * Published inside the dbNSFP install itself (params.data_dir/dbNSFP/dbNSFP), not committed under
 * assets/: that is what makes it visible to every container without a projectDir bind mount, since
 * data_dir is already mounted to /data for every process (nextflow.config's docker/singularity
 * profiles). It also ties the file's lifetime to the dbNSFP version it was generated from - a
 * version bump replaces the whole folder, and the caller subworkflow's existence check naturally
 * regenerates rather than reusing a stale file from the previous version.
 */

process GEN_DBNSFP_ALIGNED_COLUMNS {
    tag "gen-dbnsfp-aligned-columns"
    publishDir "${params.data_dir}/dbNSFP/dbNSFP", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:rebuild"

    input:
        path probe_tsv

    output:
        path "dbnsfp_transcript_aligned_columns.txt"

    script:
    """
    set -euo pipefail

    readme=\$(find /data/dbNSFP/dbNSFP -maxdepth 1 -name "*.readme.txt" | head -1)
    if [ -z "\$readme" ]; then
        echo "ERROR: no dbNSFP readme (*.readme.txt) found under /data/dbNSFP/dbNSFP" >&2
        exit 1
    fi

    gen_dbnsfp_aligned_columns.py "\$readme" dbnsfp_transcript_aligned_columns.txt "${probe_tsv}"
    """
}
