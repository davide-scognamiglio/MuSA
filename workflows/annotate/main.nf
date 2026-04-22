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

// annotation
include {PREPROCESS} from '../../subworkflows/local/preprocess'
include {ANNOTATE_GERMLINE} from '../../subworkflows/local/annotate_germline'
include {POSTPROCESS} from '../../subworkflows/local/postprocess'
include { extract_csv } from '../../lib/annot_utils.nf'

workflow ANNOTATE {

    ch_germline = extract_csv(file(params.input))

    // PREPROCESS subworkflow
    preprocessed_ch = PREPROCESS(ch_germline)

    // ANNOTATE_GERMLINE subworkflow
    annotated_ch = ANNOTATE_GERMLINE(preprocessed_ch)

    // POSTPROCESS subworkflow
    final_ch = POSTPROCESS(annotated_ch)
}


