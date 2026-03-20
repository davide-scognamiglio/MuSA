/*
 * MuSA
 * Module: RENAME_VCF_BY_PATIENT
 * Purpose: Rename final VCF based on patient ID
 */


process RENAME_VCF_BY_PATIENT {
    tag "rename-vcf"
    cpus 1
    memory "1 GB"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), file("${meta.patient}.vcf.gz")

    script:
        """
        mv ${vcf} ${meta.patient}.vcf.gz
        """
}