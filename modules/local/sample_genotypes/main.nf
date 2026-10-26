/*
 * MuSA
 * Module: SAMPLE_GENOTYPES
 * Purpose: The reported sample's own genotype as MAF columns (Zygosity, Sample_GT, Sample_DP,
 *          Sample_GQ, Sample_AD, Sample_VAF), read from its FORMAT values rather than from INFO,
 *          whose AC/AN/DP cover every sample of a joint-called VCF. See bin/sample_genotypes.py.
 */

process SAMPLE_GENOTYPES {
    tag "${meta.patient} | sample genotype"
    container "dsbioinfo/musa-helper:rebuild"
    memory { 1.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        tuple val(meta), path(maf)

    output:
        tuple val(meta), path("${meta.patient}.genotypes.maf")

    script:
        """
        sample_genotypes.py --maf ${maf} --output ${meta.patient}.genotypes.maf ${meta.mode == 'cohort' ? '--blank' : ''}
        """
}
