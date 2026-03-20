/*
 * MuSA
 * Module: BUILD_ANNOTATE_REPORT
 * Purpose: Generate HTML report/report for each patient
 */


process BUILD_ANNOTATE_REPORT {
    tag "report"
    cpus 1
    errorStrategy 'retry'
    maxRetries 2
    memory { 18.GB * task.attempt }
    container "dsbioinfo/musa-helper:latest"    
    publishDir "${params.outdir}/${params.date}/${meta.patient}", mode: "copy"

    input:
        val(meta) 
        file("${meta.patient}.filtered.maf") 
        file("${meta.patient}.raw.maf") 
    
    output:       
        tuple val(meta), 
            file("${meta.patient}_maf_dashboard.html"),  
            file("lib"), 
            file("${meta.patient}.filtered.maf"),
            file("${meta.patient}.raw.maf") 

    script:
        """
        annotate_reporter.R "${meta.patient}" "${params.workflow}" "${params.use_vep_plugins}" "${params.offline}" "${params.skip_genebe}"
        """
}