/*
 * MuSA
 * Module: BUILD_SETUP_REPORT
 * Purpose: Generate HTML report for downloaded genomic resources, and record the manifest in
 *          the data dir
 *
 * <data_dir>/dbs_manifest.yaml is what the next `setup --update_db_only` diffs against, so it
 * must say what is installed. It used to be published by MERGE_YAML, i.e. already by
 * BASIC_SETUP's merge, before EXTENDED_SETUP had downloaded anything: when an extended setup
 * then failed, the data dir claimed every entry as current and the re-run skipped the downloads
 * that never happened. This step runs last, only once every download has succeeded.
 */

process BUILD_SETUP_REPORT {
    tag "setup_report"
    container "dsbioinfo/musa-helper:rebuild-minimal"
    publishDir "${params.data_dir}", mode: 'copy', overwrite: true

    input:
        path merged_yaml

    output:
        path "setup_report.html"
        path "dbs_manifest.yaml"

    script:
    """
    logo="${projectDir}/assets/MuSA_logo.png"
    build_setup_report.py ${merged_yaml} setup_report.html \$logo "${workflow.manifest.version}"
    cp -L ${merged_yaml} dbs_manifest.yaml
    """
}