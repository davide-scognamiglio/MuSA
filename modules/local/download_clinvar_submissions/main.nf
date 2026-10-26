/*
 * MuSA
 * Module: DOWNLOAD_CLINVAR_SUBMISSIONS
 * Purpose: Index what ClinVar submitters wrote about each variant (ACMG codes named, functional
 *          evidence described), for the ClinVar_SCV_* and ClinVar_EP_codes columns
 *
 * The comments come from ClinVar's monthly submission_summary (the archived release of the same
 * month as the ClinVar VCF in the manifest). Only the index is kept (~16 MB, see
 * bin/clinvar_submissions.py); the ~380 MB summary is deleted once built.
 */


process DOWNLOAD_CLINVAR_SUBMISSIONS {
    tag "clinvar_setup"
    container "dsbioinfo/musa-helper:rebuild"
    memory { 4.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        file manifest
        path changed_entries

    output:
        file('clinvar_submissions_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "clinvar_submission_summary" "${changed_entries}" "/data/clinvar_submissions"; then
        echo "[INFO] No changes for download_clinvar_submissions -- skipping download, reusing existing data."
        cp "${manifest}" clinvar_submissions_manifest.yaml
        exit 0
    fi

    mkdir -p clinvar_submissions
    cd clinvar_submissions

    fetch_entry "\$PWD/../${manifest}" clinvar_submission_summary
    clinvar_submissions.py build "\${clinvar_submission_summary_out}" clinvar_submissions.tsv.gz
    rm "\${clinvar_submission_summary_out}"

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "clinvar_submissions" "/data/clinvar_submissions"

    mv ${manifest} clinvar_submissions_manifest.yaml
    """
}
