/*
 * MuSA
 * Module: RENOVO_ANNOTATE_VCF
 * Purpose: Annotate variants with ReNOVo and generate corresponding MAF file
 */


process RENOVO_ANNOTATE_VCF {
    tag "renovo-annotation"
    // ReNOVo is single-threaded in practice: measured median 116% cpu over 147 ClinVar chunks, so
    // params.n_core (8) reserved 8 cores to run one and starved VEP, which does scale. 18 GB stays:
    // peak_rss reached 11.8 GB. Neither directive is part of the task hash, so this does not
    // invalidate the cache.
    cpus 2
    errorStrategy 'retry'
    maxRetries 1
    memory { 18.GB * task.attempt }
    // 1.1.2 = 1.1.0 + the Renovo_implementation.py prediction-alignment fix (containers/renovo/).
    // 1.1.0/1.1.1 crash on any input holding two adjacent unscorable rows, and misplace PL_score
    // around isolated ones. Built locally; see containers/renovo/Dockerfile.
    container "dsbioinfo/renovo:1.1.2"

    input:
        tuple val(meta), file(vcf)

    output:      
        tuple val(meta), file("${meta.patient}.renovo.txt")
    
    script:
        """
        set -euo pipefail
        
        python /software/renovo/ReNOVo.py \
            -p . -a /annovar \
            -d /data/renovo_humandb \
            -b ${params.build} -c "clinvar_20250721"

        mv ReNOVo_output/${meta.patient}_ReNOVo_and_ANNOVAR_implemented.txt "${meta.patient}.renovo.txt"


        """
}