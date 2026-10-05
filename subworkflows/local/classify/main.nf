include {ENCODE_CLINVAR} from '../../../modules/local/encode_clinvar'
include {RENOVO_ADJUST_ACMG} from '../../../modules/local/renovo_adjust_acmg'

/*
 * Stage 3 of ANNOTATE: each variant's classification on one scale.
 *
 *   ENCODE_CLINVAR      ClinVar significance and review status as B / LB / VUS / LP / P and stars
 *   RENOVO_ADJUST_ACMG  GeneBe's ACMG score moved by the RENOVO 1.5 prediction for missense
 *                       variants (online and extended mode: the ACMG score comes from GeneBe,
 *                       the RENOVO prediction needs dbNSFP)
 */
workflow CLASSIFY {
    take: maf

    main:
        encoded    = ENCODE_CLINVAR(maf)
        classified = (params.offline || !params.extended) ? encoded : RENOVO_ADJUST_ACMG(encoded)

    emit:
        classified
}
