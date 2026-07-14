include {VEP_ANNOTATE_VCF} from '../../../modules/local/vep_annotate_vcf'
include {SPLIT_VCF_BY_CHR} from '../../../modules/local/split_vcf_by_chr'
include {DBNSFP_ANNOTATE_VCF_CHR} from '../../../modules/local/dbnsfp_annotate_vcf_chr'
include {GATHER_DBNSFP_TSV} from '../../../modules/local/gather_dbnsfp_tsv'
include {GENEBE_ANNOTATE_VCF} from '../../../modules/local/genebe_annotate_vcf'
include {VCF_TO_MAF} from '../../../modules/local/vcf_to_maf'
include {RENOVO_ANNOTATE_VCF} from '../../../modules/local/renovo_annotate_vcf'
include {PARSE_VEP_ANNOTATION} from '../../../modules/local/parse_vep_annotation'
include {MERGE_ANNOTATIONS} from '../../../modules/local/merge_annotations'
include {ADD_GENOME_CHANGE} from '../../../modules/local/add_genome_change'
include {ADD_REF_CONTEXT} from '../../../modules/local/add_ref_context'
include {chrom_list} from '../../../lib/annot_utils.nf'

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
         * Branch 2: dbNSFP (scattered by chromosome, gathered back to one TSV per patient)
         */
        chr_ch = Channel.fromList(chrom_list("${params.data_dir}/vep_data/reference_genome/${params.build}.fa.fai"))

        dbnsfp_shards    = SPLIT_VCF_BY_CHR(vcf.combine(chr_ch))
        dbnsfp_shard_tsv = DBNSFP_ANNOTATE_VCF_CHR(dbnsfp_shards)

        dbnsfp_tsv = GATHER_DBNSFP_TSV(
            dbnsfp_shard_tsv
                .map { meta, chr, tsv -> tuple(meta, tsv) }
                .groupTuple()
        )

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