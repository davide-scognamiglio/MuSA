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
        // The wanted chromosomes travel as ONE value, not as a channel to cross with: SPLIT_VCF_BY_CHR
        // now shards a VCF in a single pass instead of being fanned out one task per chromosome.
        chr_ch = Channel.value(chrom_list("${params.data_dir}/vep_data/reference_genome/${params.build}.fa.fai"))

        // transpose() turns (meta, [shard, shard, ...]) into one (meta, shard) per shard; the chr is
        // recovered from the filename that SPLIT_VCF_BY_CHR wrote it into, rebuilding the exact
        // (meta, chr, shard) tuple DBNSFP_ANNOTATE_VCF_CHR already expects.
        dbnsfp_shards = SPLIT_VCF_BY_CHR(vcf, chr_ch)
            .transpose()
            .map { meta, shard ->
                def m = (shard.name =~ /\.([^.]+)\.shard\.vcf$/)
                if (!m) error "SPLIT_VCF_BY_CHR produced an unparseable shard name: ${shard.name}"
                tuple(meta, m[0][1], shard)
            }
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