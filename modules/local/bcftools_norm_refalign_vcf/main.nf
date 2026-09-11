/*
 * MuSA
 * Module: BCFTOOLS_NORM_REFALIGN_VCF
 * Purpose: Normalize VCF with reference genome and left-align (no indexing)
 */


process BCFTOOLS_NORM_REFALIGN_VCF {
    tag "norm-refalign"
        cpus params.n_core
    memory "2 GB"
    container "dsbioinfo/bcftools:1.2"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("refnormalized.vcf")

    script:
        """
        bcftools norm -m-any --check-ref -w -f /data/vep_data/reference_genome/${params.build}.fa ${vcf} -Ov -o refnormalized.vcf
        """
}