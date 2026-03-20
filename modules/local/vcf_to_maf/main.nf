/*
 * MuSA
 * Module: VCF_TO_MAF
 * Purpose: Convert a VCF to a MAF file using vcf2maf
 */


process VCF_TO_MAF {
    tag "vcf2maf"
    cpus 1
    memory "1 GB"
    container "dsbioinfo/vcf2maf:latest"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.maf")

    script:
         """
        set -euo pipefail

        # Get base name of input file
        base=\$(basename "${vcf}")

        # Conditional decompress if gzipped
        if [[ "\$base" == *.gz ]]; then
            gunzip -c "${vcf}" > "\${base%.gz}.vcf"
            vcf_file="\${base%.gz}.vcf"
        else
            vcf_file="\$base"
            cp "${vcf}" "\$vcf_file"
        fi

        # Normalize chromosome names
        awk 'BEGIN{OFS="\\t"}
            /^#/ {print; next}
            {
                if (\$1 == "chrMT" || \$1 == "MT") \$1 = "chrM"
                if (\$1 !~ /^chr/) \$1 = "chr"\$1
                print
            }' "\$vcf_file" > "\${vcf_file}.with_chr.vcf"

        mv "\${vcf_file}.with_chr.vcf" "\$vcf_file"

        export REF_FASTA=/data/vep_data/reference_genome/${params.build}.fa

        perl /opt/vcf2maf.pl \
            --input-vcf "\$vcf_file" \
            --output-maf ${meta.patient}.tmp.maf \
            --ref-fasta \$REF_FASTA \
            --inhibit-vep

        tail -n +2 ${meta.patient}.tmp.maf > ${meta.patient}.maf
        """
}
