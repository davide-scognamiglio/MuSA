/*
 * MuSA
 * Module: RENOVO_ANNOTATE_VCF
 * Purpose: Annotate variants with ReNOVo and generate corresponding MAF file
 */


process RENOVO_ANNOTATE_VCF {
    tag "renovo-annotation"
    // ReNOVo is single-threaded in practice: measured median 116% cpu over 147 ClinVar chunks, so
    // params.n_core (8) reserved 8 cores to run one and starved VEP, which does scale. Neither
    // directive is part of the task hash, so tuning them does not invalidate the cache.
    cpus 2
    errorStrategy 'retry'
    maxRetries 1
    // ReNOVo's R step loads the whole ANNOVAR multianno table at once, so peak memory tracks variant
    // count almost linearly. Three measurements: 30k-variant ClinVar chunks peaked at 11.8 GB, a
    // ~67k-variant WES cohort at 26.0 GB (max over 55 samples), and a 195,519-variant sample
    // OOM-killed at both 18 GB and 36 GB. That is ~0.39 GB per 1k variants, so estimate as
    // `variants/1000 * 0.4 GB` when retuning.
    //
    // 36 GB is ~1.4x the measured 26.0 GB peak of a real exome, and the retry doubles to 72 GB, which
    // covers the ~76 GB a 195k-variant input would need. Sizing this from the OOM case instead (the
    // earlier 80 GB) over-declared by 3x, and declared memory throttles Nextflow's local-executor
    // concurrency whether or not the task uses it: at 80 GB only 3 ReNOVo tasks fit a 251 GB box, at
    // 36 GB six do. Do not cap this with a process.resourceLimits below 72 GB or the retry is moot.
    //
    // An OOM here is easy to misread: the container dies with a bare "Killed" after tidyverse loads,
    // then ReNOVo prints "Output generated!" unconditionally while ReNOVo_output/ is empty, so the mv
    // below fails with a misleading "No such file or directory".
    memory { 36.GB * task.attempt }
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