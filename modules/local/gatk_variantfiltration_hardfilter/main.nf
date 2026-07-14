/*
 * MuSA
 * Module: GATK_VARIANTFILTRATION_HARDFILTER
 * Purpose: Apply hard filtering using GATK VariantFiltration and index VCF
 */


process GATK_VARIANTFILTRATION_HARDFILTER {
    tag "hard-filter"
    cpus 2
    memory "4 GB"
    container "dsbioinfo/gatk:latest"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("hardfiltered.vcf.gz")

    script:
        """
        # Index input VCF before filtering (bgzip-compressed, from BCFTOOLS_FILTER_SYMBOLIC_ALLELES)
        tabix -p vcf ${vcf}

        # Apply GATK hard filters
        gatk VariantFiltration \
            -V ${vcf} \
            -filter "QD < 2.0" --filter-name "QD2" \
            -filter "QUAL < 30.0" --filter-name "QUAL30" \
            -filter "SOR > 3.0" --filter-name "SOR3" \
            -filter "FS > 60.0" --filter-name "FS60" \
            -filter "MQ < 40.0" --filter-name "MQ40" \
            -filter "MQRankSum < -12.5" --filter-name "MQRankSum-12.5" \
            -filter "ReadPosRankSum < -8.0" --filter-name "ReadPosRankSum-8" \
            -O filtered_temp.vcf

        # Keep only unfiltered variants. GATK auto-indexes a .vcf.gz -O target itself
        # (produces hardfiltered.vcf.gz.tbi alongside), so no separate tabix call is needed here —
        # one used to follow this and failed ("the index file exists") against GATK's own index.
        gatk SelectVariants \
            -V filtered_temp.vcf \
            --exclude-filtered \
            -O hardfiltered.vcf.gz
        """
}