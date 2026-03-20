/*
 * MuSA
 * Module: BCFTOOLS_FILTER_NONVARIANT_GT
 * Purpose: Keep only variant genotypes (remove homozygous reference GT="0/0")
 */


process BCFTOOLS_FILTER_NONVARIANT_GT {
    tag "filter-nonvariant"
    cpus 1
    memory "2 GB"
    container "dsbioinfo/bcftools:1.2"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("variant_only.vcf.gz")

    script:
        """
        bcftools view -i 'GT!="0/0"' ${vcf} -Oz -o variant_only.vcf.gz
        """
}