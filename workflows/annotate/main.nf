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
include {SOFTWARE_VERSIONS} from '../../modules/local/software_versions'
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

    // The tools this run uses, each asked for its version in the image it runs in. The images
    // repeat the modules' own container directives: keep the two in step.
    def images = [
        ['ensembl-vep', params.vep_container],
        ['vcf2maf',     'dsbioinfo/vcf2maf:rebuild'],
        ['musa-helper', 'dsbioinfo/musa-helper:rebuild'],
        ['musa-report', 'dsbioinfo/musa-helper:rebuild-minimal'],
    ]
    if (!params.skip_bcftools) {
        images << ['bcftools', 'dsbioinfo/bcftools:1.2']
        if (params.vcf_format == 'sarek') {
            images << ['gatk', 'dsbioinfo/gatk:latest']
        }
    }
    if (params.extended) {
        images << ['renovo-rebuild', params.renovo_container]
    }
    if (!params.offline && !params.skip_genebe) {
        images << ['genebe', 'genebe/pygenebe:0.1.15']
    }
    versions_yml = SOFTWARE_VERSIONS(channel.fromList(images))
        .collectFile(name: 'software_versions.yml', storeDir: "${params.outdir}/${params.date}", sort: { f -> f.name })
        .first()

    ch_germline = extract_csv(file(params.input))

    preprocessed = PREPROCESS(ch_germline)
    variants     = ANNOTATE_VARIANTS(preprocessed)
    genes        = ANNOTATE_GENES(variants)
    classified   = CLASSIFY(genes)
    FILTER_AND_REPORT(classified, sources_json, versions_yml)
}
