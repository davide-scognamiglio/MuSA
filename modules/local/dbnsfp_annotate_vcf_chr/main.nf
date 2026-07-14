/*
 * nf-core/variantannotation
 * Module: DBNSFP_ANNOTATE_VCF_CHR
 * Purpose: Annotate a single-chromosome VCF shard using dbNSFP
 */

process DBNSFP_ANNOTATE_VCF_CHR {
    tag "dbNSFP-annotation-${meta.patient}-${chr}"
    cpus params.dbnsfp_shard_cpus
    maxForks params.dbnsfp_max_forks
    errorStrategy 'retry'
    maxRetries 3
    memory { (4.GB * params.dbnsfp_shard_cpus) * task.attempt }
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), val(chr), path(shard_vcf)

    output:
        tuple val(meta), val(chr), path("${meta.patient}.${chr}.dbnsfp.tsv")

    script:
    def heap_mb = (task.memory.toMega() * 0.8) as long
    """
    if [ "\$(grep -vc '^#' ${shard_vcf})" -eq 0 ]; then
        touch "${meta.patient}.${chr}.dbnsfp.tsv"
    else
        jar=\$(find /data/dbNSFP/dbNSFP -maxdepth 1 -name "*.jar" | head -1)
        jar_name=\$(basename "\$jar" .jar)
        chr_bare="${chr}"
        chr_bare="\${chr_bare#chr}"

        java -Xmx${heap_mb}m -cp /data/dbNSFP/dbNSFP "\$jar_name" \
            -i ${shard_vcf} \
            -o "${meta.patient}.${chr}.dbnsfp.tsv" \
            -c "\$chr_bare" \
            -p
    fi
    """
}
