/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CONFIG FILES
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

params.date = new java.util.Date().format('yyMMdd')


/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    IMPORT LOCAL MODULES/SUBWORKFLOWS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

include {PREPROCESS} from '../../subworkflows/local/preprocess'
include {ANNOTATE_VARIANTS} from '../../subworkflows/local/annotate_variants'
include {ANNOTATE_GENES} from '../../subworkflows/local/annotate_genes'
include {CLASSIFY} from '../../subworkflows/local/classify'
include {FILTER_AND_REPORT} from '../../subworkflows/local/filter_and_report'
include { extract_csv; annotation_sources; log_annotation_sources } from '../../lib/annot_utils.nf'

/*
 * VCF -> preprocessing -> variant-level annotation -> gene-level annotation -> classification ->
 * filtered MAF and report. The stage names are what the terminal shows for each task
 * (ANNOTATE:ANNOTATE_GENES:CLINGEN_ANNOTATE_MAF), so they say what each step adds.
 */
workflow ANNOTATE {

    // Which sources this run annotates from, with the versions installed in --data_dir: printed
    // now, and handed to the report for its Sources tab.
    def sources = annotation_sources()
    log_annotation_sources(sources)
    def sources_json = file("${workflow.workDir}/musa_annotation_sources.json")
    sources_json.text = groovy.json.JsonOutput.prettyPrint(groovy.json.JsonOutput.toJson(sources))

    ch_germline = extract_csv(file(params.input))

    preprocessed = PREPROCESS(ch_germline)
    variants     = ANNOTATE_VARIANTS(preprocessed)
    genes        = ANNOTATE_GENES(variants)
    classified   = CLASSIFY(genes)
    FILTER_AND_REPORT(classified, sources_json)
}
