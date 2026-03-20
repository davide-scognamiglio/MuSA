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
        # Index input VCF before filtering
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
            -O filtered_temp.vcf.gz

        # Keep only unfiltered variants
        gatk SelectVariants \
            -V filtered_temp.vcf.gz \
            --exclude-filtered \
            -O hardfiltered.vcf.gz

        # Index final output
        tabix -p vcf hardfiltered.vcf.gz
        """
}