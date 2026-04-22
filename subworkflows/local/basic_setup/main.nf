include { DOWNLOAD_MANIFEST } from '../../../modules/local/download_manifest'
include { DOWNLOAD_ANNOVAR_DB } from '../../../modules/local/download_annovar_db'
include { DOWNLOAD_VEP_CACHE } from '../../../modules/local/download_vep_cache'
include { DOWNLOAD_REFGENOME } from '../../../modules/local/download_refgenome'
include { DOWNLOAD_DBNSFP } from '../../../modules/local/download_dbnsfp'
include { MERGE_YAML as MERGE_BASIC_YAML } from '../../../modules/local/merge_yaml'

workflow BASIC_SETUP {

    main:

        // Step 1: download manifest
        manifest_ch = DOWNLOAD_MANIFEST()

        // Step 2: download modules in parallel, each consuming the manifest
        annovar_ch = DOWNLOAD_ANNOVAR_DB(manifest_ch)
        vep_ch     = DOWNLOAD_VEP_CACHE(manifest_ch)
        dbnsfp_ch  = DOWNLOAD_DBNSFP(manifest_ch)
        refgen_ch  = DOWNLOAD_REFGENOME(manifest_ch)
        merged_input = annovar_ch
            .mix(vep_ch, dbnsfp_ch, refgen_ch)
            .map { dir, yaml -> yaml }
            .collect()

        merged_yaml = MERGE_BASIC_YAML(merged_input)

    emit:
        merged_yaml
}