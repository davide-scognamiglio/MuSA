include {ENCODE_CLINVAR} from '../../../modules/local/encode_clinvar'
include {CLINVAR_RESIDUES} from '../../../modules/local/clinvar_residues'
include {CLINVAR_SUBMISSIONS} from '../../../modules/local/clinvar_submissions'
include {RENOVO_ADJUST_ACMG} from '../../../modules/local/renovo_adjust_acmg'

/*
 * Stage 3 of ANNOTATE: each variant's classification on one scale.
 *
 *   ENCODE_CLINVAR      ClinVar significance and review status as B / LB / VUS / LP / P and stars
 *   CLINVAR_RESIDUES    ClinVar evidence at the variant's residue: the same amino-acid change
 *                       pathogenic through another nucleotide change (PS1), or another change at
 *                       the residue pathogenic (PM5)
 *   CLINVAR_SUBMISSIONS what ClinVar submitters wrote: ACMG codes they name (PS3/BS3), functional
 *                       studies they describe and with what result, the expert panel's own codes
 *                       kept apart
 *   RENOVO_ADJUST_ACMG  GeneBe's ACMG score moved by the RENOVO 1.5 prediction for missense
 *                       variants (online and extended mode: the ACMG score comes from GeneBe,
 *                       the RENOVO prediction needs dbNSFP)
 */
workflow CLASSIFY {
    take: maf

    main:
        encoded    = CLINVAR_SUBMISSIONS(CLINVAR_RESIDUES(ENCODE_CLINVAR(maf)))
        classified = (params.offline || !params.extended) ? encoded : RENOVO_ADJUST_ACMG(encoded)

    emit:
        classified
}
