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
        transcripts   // <patient>.transcripts.tsv.gz (TRANSCRIPTS_TABLE), for the transcript selector
        sources_json  // this run's annotation sources (lib/annot_utils.nf annotation_sources)
        versions_yml  // this run's tool versions (SOFTWARE_VERSIONS)

    main:
        filtered = FILTER_VARIANTS(maf)
        with_tx  = filtered.map { meta, f, raw -> [meta.patient, meta, f, raw] }
            .join(transcripts.map { meta, tx -> [meta.patient, tx] })
            .map { _patient, meta, f, raw, tx -> [meta, f, raw, tx] }
        report   = BUILD_ANNOTATE_REPORT(with_tx, sources_json, versions_yml)

    emit:
        report
}
