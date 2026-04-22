/*
 * MuSA
 * Module: NORMALIZE_CHR
 * Purpose: Normalize Chr format to UCSC
 */

process NORMALIZE_CHR {
    tag "normalize_chr"
    cpus 1
    memory "1 GB"
    container "dsbioinfo/vcf2maf:rebuild"

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("chr_normalized.vcf")

    script:
        """
        set -euo pipefail
        ls -lah

        # Default: assume vcf_file is same as input
        vcf_file="${vcf}"

        # Decompress to temporary file if gzipped
        if head -c 2 "${vcf}" | od -An -t x1 | grep -q "1f 8b"; then
            echo "GZIPPED!"
            tmp_vcf="\$(mktemp --suffix=.vcf)"
            gunzip -c "${vcf}" > "\$tmp_vcf"
            vcf_file="\$tmp_vcf"
        fi

        echo "Using VCF: \$vcf_file"

        # Output normalized VCF (new file in work dir)
        normalized_vcf="\$vcf_file.normalized.vcf"

        # Normalize chromosomes
        awk 'BEGIN{OFS="\\t"} /^#/ {print; next} {if (\$1=="chrMT"||\$1=="MT") \$1="chrM"; if (\$1 !~ /^chr/) \$1="chr"\$1; print}' "\$vcf_file" > "chr_normalized.vcf" 
    """
   
}
