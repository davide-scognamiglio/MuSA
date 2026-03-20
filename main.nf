#!/usr/bin/env nextflow
nextflow.enable.dsl=2


// Load and display ASCII banner
def bannerFile = file('assets/banner.txt')

if (bannerFile.exists()) {
    println bannerFile.text
}

/*

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    VALIDATE & PRINT PARAMETER SUMMARY
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/
include { validateParameters; paramsSummaryLog; samplesheetToList } from 'plugin/nf-schema'

// Validate input parameters
validateParameters()

// Print summary of supplied parameters
log.info paramsSummaryLog(workflow)

// Create a new channel of metadata from a sample sheet passed to the pipeline through the --input parameter
// ch_input = Channel.fromList(samplesheetToList(params.input, "assets/schema_input.json"))


// Set alternate build names
if(params.build == "hg38") {
    params.build_alt_name = "GRCh38"
} else if(params.build == "hg19") {
    params.build_alt_name = "GRCh37"
}

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

    switch (params.workflow) {
        case "":
        case "annotate":
            ANNOTATE()
            break

        case "setup":
            SETUP()
            break

        default:
            error """
            ──────────────────── ERROR ────────────────────
            Invalid value for --workflow: '${params.workflow}'.

            Accepted values:
            • annotate
            • setup

            Example:
            nextflow run main.nf -c config/annotation.config --workflow annotate    
            ───────────────────────────────────────────────
            """
    }
}
