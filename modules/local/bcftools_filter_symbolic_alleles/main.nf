/*
 * MuSA
 * Module: BCFTOOLS_FILTER_SYMBOLIC_ALLELES
 * Purpose: Remove symbolic alleles (ALT="*") from VCF
 */


process BCFTOOLS_FILTER_SYMBOLIC_ALLELES {
    tag "filter-symbolic"
    cpus 1
    memory "2 GB"
    container "dsbioinfo/bcftools:1.2"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("filtered_symbolic.vcf.gz")

    script:
        """
        bcftools view -e 'ALT="*"' ${vcf} -Oz -o filtered_symbolic.vcf.gz
        """
}