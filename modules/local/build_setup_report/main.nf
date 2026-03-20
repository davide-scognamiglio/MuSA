/*
 * MuSA
 * Module: BUILD_SETUP_REPORT
 * Purpose: Generate HTML report/report for each patient
 */

process BUILD_SETUP_REPORT {

    tag "setup_report"
    
    input:
        tuple val(download_dirs)

    output:
        path "setup_report.html"

    script:
    """
    echo ${download_dirs}
    mkdir -p report_tmp
    cp -r ${download_dirs} report_tmp/
    setup_reporter.sh setup_report.html ${download_dirs}
    """
}
