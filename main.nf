#!/usr/bin/env nextflow
nextflow.enable.dsl=2


/*

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    VALIDATE & PRINT PARAMETER SUMMARY
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { validateParameters; paramsSummaryLog; samplesheetToList } from 'plugin/nf-schema'

// Create a new channel of metadata from a sample sheet passed to the pipeline through the --input parameter
// ch_input = Channel.fromList(samplesheetToList(params.input, "assets/schema_input.json"))

// Set alternate build names. hg38 is the only accepted build (checked at the top of the workflow
// block), so its alternate name is fixed.
params.build_alt_name = "GRCh38"


/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    INCLUDE TOP-LEVEL WORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include { ANNOTATE } from './workflows/annotate/main.nf'
include { SETUP } from './workflows/setup/main.nf'

/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    PIPELINE ENTRYPOINT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

workflow {

    // Nextflow's strict syntax (default from 26.04) allows no statements outside a workflow, process
    // or function, so the start-of-run steps live here rather than at the top of the script.

    // Load and display ASCII banner
    def bannerFile = file('assets/banner.txt')
    if (bannerFile.exists()) {
        println bannerFile.text
    }

    // Validate input parameters
    validateParameters()

    // Print summary of supplied parameters
    log.info paramsSummaryLog(workflow)

    if (params.build != "hg38") {
        error "Currently, we only support hg38 build. We will likely support T2T build in the future"
    }

    if (params.workflow == "" || params.workflow == "annotate") {
        ANNOTATE()
    }
    else if (params.workflow == "setup") {
        // Create --data_dir as the launching user before any container mounts it. Docker creates a
        // missing mount source as root, and Nextflow, which publishes the setup report as the user,
        // could then not write into it.
        if (params.data_dir) {
            file(params.data_dir).mkdirs()
        }
        checkDbnsfpSource()
        SETUP()
    }
    else {
            error """
            ──────────────────── ERROR ────────────────────
            Invalid value for --workflow: '${params.workflow}'.

            Accepted values:
            • annotate
            • setup

            Example:
            nextflow run davide-scognamiglio/MuSA --workflow annotate
            ───────────────────────────────────────────────
            """
    }

    // Captured here: once the handler lives in the workflow block rather than at the top of the
    // script, `workflow` and `params` no longer resolve inside it when it fires.
    def wf = workflow
    def outdir = params.outdir
    wf.onComplete {
        log.info """
        ────────────────────────────────────────────────
        Pipeline completed at : ${wf.complete}
        Duration              : ${wf.duration}
        Success               : ${wf.success}
        Exit status           : ${wf.exitStatus}
        Work dir              : ${wf.workDir}
        Output dir            : ${outdir}
        ────────────────────────────────────────────────
        """.stripIndent()
    }
}

/*
 * dbNSFP is distributed only to registered users, so the public manifest leaves its url empty and
 * the user supplies the download (--dbnsfp_url or --dbnsfp_zip). Checked before anything starts:
 * DOWNLOAD_DBNSFP runs next to the multi-hour VEP cache download, and failing there would waste it.
 * --update_db_only is left to DOWNLOAD_DBNSFP, which needs a source only if dbNSFP changed.
 */
def checkDbnsfpSource() {
    if (params.dbnsfp_zip || params.dbnsfp_url || params.update_db_only) {
        return
    }
    // A custom --dbs_manifest may still carry its own dbNSFP url.
    def entry = (file(params.dbs_manifest).text =~ /(?ms)^  dbnsfp:\s*\n(.*?)(?=^  \S|\z)/)
    def url = entry.find() ? ((entry.group(1) =~ /(?m)^\s+url:\s*"?([^"\s]*)"?/).with { it.find() ? it.group(1) : "" }) : ""
    if (!url) {
        error """
        ──────────────────── ERROR ────────────────────
        dbNSFP needs a download source.

        dbNSFP is free for academic, non-commercial use, but it is distributed
        only to registered users, so MuSA cannot download it for you.
          1. Register at https://www.dbnsfp.org/download (institutional email).
          2. Then either
             --dbnsfp_url '<your dbNSFP download link>'
             or download the zip yourself and pass
             --dbnsfp_zip /path/to/dbNSFP5.3.1a.zip
        ───────────────────────────────────────────────
        """
    }
}
