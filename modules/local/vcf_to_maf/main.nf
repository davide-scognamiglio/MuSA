/*
 * MuSA
 * Module: VCF_TO_MAF
 * Purpose: Convert a VCF to a MAF file using vcf2maf
 */


process VCF_TO_MAF {
    tag "vcf2maf"
    cpus 1
    memory "1 GB"
    container "dsbioinfo/vcf2maf:rebuild"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.maf")

    script:
        """
        set -euo pipefail


        export REF_FASTA=/data/vep_data/reference_genome/${params.build}.fa

        perl /opt/vcf2maf.pl \
            --input-vcf ${vcf} \
            --output-maf ${meta.patient}.tmp.maf \
            --ref-fasta \$REF_FASTA \
            --inhibit-vep


        tail -n +2 ${meta.patient}.tmp.maf > ${meta.patient}.maf
        """
}


