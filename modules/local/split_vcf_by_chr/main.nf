/*
 * MuSA
 * Module: SPLIT_VCF_BY_CHR
 * Purpose: Restrict a VCF to a single chromosome (dbNSFP per-chromosome scatter)
 */

process SPLIT_VCF_BY_CHR {
    tag "split-${meta.patient}-${chr}"
    cpus 1
    memory "1 GB"
    container "dsbioinfo/bcftools:1.2"

    input:
        tuple val(meta), path(vcf), val(chr)

    output:
        tuple val(meta), val(chr), path("${meta.patient}.${chr}.shard.vcf")

    script:
    """
    bcftools view -t ${chr} ${vcf} -Ov -o ${meta.patient}.${chr}.shard.vcf
    """
}
