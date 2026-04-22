/*
 * MuSA
 * Module: RENOVO_ANNOTATE_VCF
 * Purpose: Annotate variants with ReNOVo and generate corresponding MAF file
 */


process RENOVO_ANNOTATE_VCF {
    tag "renovo-annotation"
    cpus 1
    errorStrategy 'retry'
    maxRetries 1
    memory { 18.GB * task.attempt }
    container "dsbioinfo/renovo:1.1.0"

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