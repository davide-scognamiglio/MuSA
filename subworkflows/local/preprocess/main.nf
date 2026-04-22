
include {NORMALIZE_CHR} from '../../../modules/local/normalize_chr'
include {BCFTOOLS_NORM_SPLIT_MULTIALLELIC} from '../../../modules/local/bcftools_norm_split_multiallelic'
include {BCFTOOLS_FILTER_SYMBOLIC_ALLELES} from '../../../modules/local/bcftools_filter_symbolic_alleles'
include {GATK_VARIANTFILTRATION_HARDFILTER} from '../../../modules/local/gatk_variantfiltration_hardfilter'
include {BCFTOOLS_NORM_REFALIGN_VCF} from '../../../modules/local/bcftools_norm_refalign_vcf'
include {BCFTOOLS_FILTER_NONVARIANT_GT} from '../../../modules/local/bcftools_filter_nonvariant_gt'
include {RENAME_VCF_BY_PATIENT} from '../../../modules/local/rename_vcf_by_patient'


workflow PREPROCESS {

    take: vcf 

    main:
        ch1 = NORMALIZE_CHR(vcf)
        // If skipping BCFTOOLS, pass input directly
        if (params.skip_bcftools) {
            ch_for_next = ch1
        } else {
            // Mandatory normalization and splitting
            ch2 = BCFTOOLS_NORM_SPLIT_MULTIALLELIC(ch1)
            ch3 = BCFTOOLS_FILTER_SYMBOLIC_ALLELES(ch2)

            // Optional hardfiltering for sarek VCFs
            if (params.vcf_format == "sarek") {
                ch4 = GATK_VARIANTFILTRATION_HARDFILTER(ch3)
                ch_for_next = ch4
            } else {
                ch_for_next = ch3
            }

            // Mandatory normalization, filtering, and renaming
            ch5 = BCFTOOLS_NORM_REFALIGN_VCF(ch_for_next)
            ch6 = BCFTOOLS_FILTER_NONVARIANT_GT(ch5)
            ch_for_next = ch6
        }

        // Renaming is always applied
        ch7 = RENAME_VCF_BY_PATIENT(ch_for_next)

    emit:
        ch7
}
