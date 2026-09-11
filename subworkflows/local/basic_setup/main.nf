include { DOWNLOAD_MANIFEST } from '../../../modules/local/download_manifest'
include { DIFF_MANIFEST } from '../../../modules/local/diff_manifest'
include { DOWNLOAD_ANNOVAR_DB } from '../../../modules/local/download_annovar_db'
include { DOWNLOAD_VEP_CACHE } from '../../../modules/local/download_vep_cache'
include { DOWNLOAD_REFGENOME } from '../../../modules/local/download_refgenome'
include { DOWNLOAD_DBNSFP } from '../../../modules/local/download_dbnsfp'
include { DOWNLOAD_CLINVAR } from '../../../modules/local/download_clinvar'
include { DOWNLOAD_CLINGEN } from '../../../modules/local/download_clingen'
include { MERGE_YAML as MERGE_BASIC_YAML } from '../../../modules/local/merge_yaml'
include { REFRESH_DBNSFP_ALIGNED_COLUMNS } from '../refresh_dbnsfp_aligned_columns'

workflow BASIC_SETUP {

    main:

        // Step 1: stage manifest (params.dbs_manifest: remote http(s) URL or local file path)
        manifest_ch = DOWNLOAD_MANIFEST(file(params.dbs_manifest))

        // Step 1b: update-db mode — diff the new manifest against the previously
        // persisted manifest so DOWNLOAD_* modules below can skip unchanged entries.
        // Outside update-db mode, changed_entries is the NO_FILE sentinel: every
        // module's should_skip_module() check always resolves to "do not skip".
        if (params.update_db_only) {
            lock_path = "${params.data_dir}/dbs_manifest.yaml"
            old_manifest = file(lock_path).exists() ? file(lock_path) : file("${projectDir}/assets/NO_FILE")
            diff_out = DIFF_MANIFEST(old_manifest, manifest_ch)
            changed_entries_ch = diff_out.changed
            manifest_ch = diff_out.manifest
        } else {
            changed_entries_ch = file("${projectDir}/assets/NO_FILE")
        }

        // Step 2: download modules in parallel, each consuming the manifest + changed-entries gate
        annovar_ch = DOWNLOAD_ANNOVAR_DB(manifest_ch, changed_entries_ch)
        vep_ch     = DOWNLOAD_VEP_CACHE(manifest_ch, changed_entries_ch)
        dbnsfp_ch  = DOWNLOAD_DBNSFP(manifest_ch, changed_entries_ch)
        refgen_ch  = DOWNLOAD_REFGENOME(manifest_ch, changed_entries_ch)
        clinvar_ch = DOWNLOAD_CLINVAR(manifest_ch, changed_entries_ch)
        clingen_ch = DOWNLOAD_CLINGEN(manifest_ch, changed_entries_ch)
        merged_input = annovar_ch
            .mix(vep_ch, dbnsfp_ch, refgen_ch, clinvar_ch, clingen_ch)
            .collect()

        merged_yaml = MERGE_BASIC_YAML(merged_input)

        // Step 3: rebuild dbnsfp_transcript_aligned_columns.txt when dbNSFP changed (or was never
        // built for the current install). No-ops instantly otherwise — see the subworkflow's own
        // doc comment for why it is safe to call unconditionally here.
        REFRESH_DBNSFP_ALIGNED_COLUMNS(dbnsfp_ch, refgen_ch)

    emit:
        merged_yaml
        changed_entries = changed_entries_ch
}
