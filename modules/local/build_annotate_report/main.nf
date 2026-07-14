/*
 * MuSA
 * Module: BUILD_ANNOTATE_REPORT
 * Purpose: Generate HTML report/report for each patient
 */


process BUILD_ANNOTATE_REPORT {
    tag "report"
        cpus params.n_core
    errorStrategy 'retry'
    maxRetries 2
    memory { 18.GB * task.attempt }
    container "dsbioinfo/musa-helper:rebuild-minimal"    
    publishDir "${params.outdir}/${params.date}/${meta.patient}", mode: "copy"

    input:
        val(meta) 
        file("${meta.patient}.filtered.maf") 
        file("${meta.patient}.raw.maf") 
    
    output:       
        tuple val(meta), 
            file("${meta.patient}_maf_dashboard.html"),  
            file("${meta.patient}.filtered.maf"),
            file("${meta.patient}.raw.maf") 

    script:
        """
        logo="${projectDir}/assets/MuSA_logo.png"
        build_annotate_report.py "${meta.patient}" "${params.use_vep_plugins}" \
        "${params.offline}" "${params.skip_genebe}" "\$logo"
        """
}