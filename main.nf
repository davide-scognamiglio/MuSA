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
