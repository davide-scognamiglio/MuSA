/*
 * MuSA
 * Module: DIFF_MANIFEST
 * Purpose: Compare a newly-staged manifest against the previously persisted
 * manifest (data_dir/dbs_manifest.yaml) and list which entry keys
 * changed (version/expected_sha256), for --update_db_only selective re-download.
 */

process DIFF_MANIFEST {
    tag "diff-manifest"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        path(old_manifest, stageAs: 'old_manifest.yaml')
        path(new_manifest)

    output:
        path("changed_entries.txt"), emit: changed
        path(new_manifest), emit: manifest

    script:
    """
    diff_manifest.py ${old_manifest} ${new_manifest} changed_entries.txt
    """
}
