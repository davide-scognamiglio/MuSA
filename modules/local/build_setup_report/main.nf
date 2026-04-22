/*
 * MuSA
 * Module: BUILD_SETUP_REPORT
 * Purpose: Generate HTML report for downloaded genomic resources
 */

process BUILD_SETUP_REPORT {
    tag "setup_report"
    publishDir "${params.data_dir}", mode: 'copy', overwrite: true

    input:
        path merged_yaml

    output:
        path "setup_report.html"

    script:
    """
    logo="${projectDir}/assets/MuSA_logo.png"
    build_setup_report.py ${merged_yaml} setup_report.html \$logo
    """
}