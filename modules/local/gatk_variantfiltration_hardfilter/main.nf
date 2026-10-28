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
        set -euo pipefail

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

        # Keep only unfiltered variants.
        gatk SelectVariants \
            -V filtered_temp.vcf \
            --exclude-filtered \
            -O selected.vcf

        # GATK writes the sample columns sorted by name, which undoes SELECT_MEMBERS' order (proband
        # first, then samplesheet order). PARSE_VEP_ANNOTATION picks members by name, so this is a
        # second line of defence: every later step sees the columns in the order they came in.
        tabix -H ${vcf} | tail -n 1 > input_samples.txt
        awk -F'\t' -v OFS='\t' '
            NR == FNR { n = 0; for (i = 10; i <= NF; i++) want[++n] = \$i; next }
            /^##/ { print; next }
            /^#CHROM/ {
                for (i = 10; i <= NF; i++) at[\$i] = i
                for (i = 1; i <= n; i++) {
                    if (!(want[i] in at)) { print "[ERROR] sample " want[i] " lost by GATK" > "/dev/stderr"; exit 1 }
                    src[i] = at[want[i]]
                }
            }
            {
                line = \$1
                for (i = 2; i <= 9 && i <= NF; i++) line = line OFS \$i
                for (i = 1; i <= n; i++) line = line OFS \$(src[i])
                print line
            }' input_samples.txt selected.vcf | bgzip -c > hardfiltered.vcf.gz
        tabix -p vcf hardfiltered.vcf.gz
        """
}