include {CLEAN_COLUMNS} from '../../../modules/local/clean_columns'
include {DBNSFP_GENE_ANNOTATE_MAF} from '../../../modules/local/dbnsfp_gene_annotate_maf'
include {CLINGEN_ANNOTATE_MAF} from '../../../modules/local/clingen_annotate_maf'
include {FILTER_VARIANTS} from '../../../modules/local/filter_variants'
include {ENCODE_CLINVAR} from '../../../modules/local/encode_clinvar'
include {RENOVO_ADJUST_ACMG} from '../../../modules/local/renovo_adjust_acmg'
include {BUILD_ANNOTATE_REPORT} from '../../../modules/local/build_annotate_report'

workflow POSTPROCESS {
    take: annotated_maf

    main:
    ch1 = CLEAN_COLUMNS(annotated_maf)
    // Gene-level dbNSFP first, then ClinGen: ClinGen's dosage values are authoritative and must
    // overwrite the gene file's older ClinGen_Haploinsufficiency_* copies.
    ch1a = DBNSFP_GENE_ANNOTATE_MAF(ch1)
    ch1b = CLINGEN_ANNOTATE_MAF(ch1a)
    ch2 = ENCODE_CLINVAR(ch1b)
    ch3  = params.offline ? ch2 : RENOVO_ADJUST_ACMG(ch2)
    ch4 = FILTER_VARIANTS(ch3)
    ch5 = BUILD_ANNOTATE_REPORT(ch4)

    emit:
        ch5
}
