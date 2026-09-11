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
    // Deliberately NOT derived from dbnsfp_shard_cpus: the heap below is rendered into the script, so
    // tying memory to the cpu count would rewrite the command (and drop every task's cache) each time
    // the scatter width is tuned. 8 GB is the measured need: peak_rss tops out at 5.1 GB on the worst
    // chromosome and is ~0 for the many empty shards.
    memory { 8.GB * task.attempt }
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
