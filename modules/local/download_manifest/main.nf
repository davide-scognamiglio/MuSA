/*
 * MuSA
 * Module: DOWNLOAD_MANIFEST
 * Purpose: Stage the manifest YAML for downstream modules.
 * params.dbs_manifest may be a remote http(s) URL (Nextflow stages it natively)
 * or a local file path (e.g. a user-supplied custom manifest overriding DB versions).
 */

process DOWNLOAD_MANIFEST {

    tag "manifest_download"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        path(manifest_src, stageAs: 'input_manifest.yaml')

    output:
        file("dbs_manifest.yaml")  // will be used by downstream modules

    script:
    """
    cp -L "${manifest_src}" dbs_manifest.yaml
    """
}