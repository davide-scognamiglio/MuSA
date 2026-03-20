/*
 * MuSA
 * Module: BCFTOOLS_NORM_SPLIT_MULTIALLELIC
 * Purpose: Normalize VCF and split multi-allelic variants using bcftools
 */


process BCFTOOLS_NORM_SPLIT_MULTIALLELIC {
    tag "normalize-split"
    cpus 1
    memory "2 GB"
    container "dsbioinfo/bcftools:1.2"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("normalized.vcf.gz")

    script:
        """
        bcftools norm -m-any ${vcf} -Oz -o normalized.vcf.gz
        """
}