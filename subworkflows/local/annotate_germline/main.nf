include {VEP_ANNOTATE_VCF} from '../../../modules/local/vep_annotate_vcf'
include {DBNSFP_ANNOTATE_VCF} from '../../../modules/local/dbnsfp_annotate_vcf'
include {GENEBE_ANNOTATE_VCF} from '../../../modules/local/genebe_annotate_vcf'
include {VCF_TO_MAF} from '../../../modules/local/vcf_to_maf'
include {RENOVO_ANNOTATE_VCF} from '../../../modules/local/renovo_annotate_vcf'
include {PARSE_VEP_ANNOTATION} from '../../../modules/local/parse_vep_annotation'
include {MERGE_ANNOTATIONS} from '../../../modules/local/merge_annotations'
include {ADD_GENOME_CHANGE} from '../../../modules/local/add_genome_change'
include {ADD_REF_CONTEXT} from '../../../modules/local/add_ref_context'

workflow ANNOTATE_GERMLINE {

    take: vcf

    main:

        /*
         * Branch 1: VEP pipeline
         */
        vep_vcf   = VEP_ANNOTATE_VCF(vcf)
        vep_gene  = params.offline ? vep_vcf : GENEBE_ANNOTATE_VCF(vep_vcf)
        vep_tsv   = PARSE_VEP_ANNOTATION(vep_gene)

        /*
         * Branch 2: dbNSFP
         */
        dbnsfp_tsv = DBNSFP_ANNOTATE_VCF(vcf)

        /*
         * Branch 3: Renovo
         */
        renovo_tsv = RENOVO_ANNOTATE_VCF(vcf)

        /*
         * Branch 4: vcf2maf
         */
        maf = VCF_TO_MAF(vcf)
        maf_g_change = ADD_GENOME_CHANGE(maf)
        maf_context = ADD_REF_CONTEXT(maf_g_change)

        /*
         * Fan-in
         */
        joined =
            vep_tsv
            .join(dbnsfp_tsv)
            .join(renovo_tsv)
            .join(maf_context)

        merged = MERGE_ANNOTATIONS(joined)

    emit:
        merged
}