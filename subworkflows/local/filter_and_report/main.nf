include {FILTER_VARIANTS} from '../../../modules/local/filter_variants'
include {BUILD_ANNOTATE_REPORT} from '../../../modules/local/build_annotate_report'

/*
 * Stage 4 of ANNOTATE: the filtered MAF and the patient report.
 *
 *   FILTER_VARIANTS        gene panel, HPO gene panel (JAX HPO API, online mode), frequency
 *   BUILD_ANNOTATE_REPORT  the HTML report, whose Sources tab lists what this run annotated from
 */
workflow FILTER_AND_REPORT {
    take:
        maf
        sources_json  // this run's annotation sources (lib/annot_utils.nf annotation_sources)

    main:
        filtered = FILTER_VARIANTS(maf)
        report   = BUILD_ANNOTATE_REPORT(filtered[0], filtered[1], filtered[2], sources_json)

    emit:
        report
}
