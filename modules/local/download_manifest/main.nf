/*
 * MuSA
 * Module: DOWNLOAD_MANIFEST
 * Purpose: Download manifest YAML for downstream modules
 */

process DOWNLOAD_MANIFEST {

    tag "manifest_download"
    container "dsbioinfo/musa-helper:rebuild" 

    output:
        file("dbs_manifest.yaml")  // will be used by downstream modules

    script:
    """
    echo "Downloading manifest from ${params.dbs_manifest}..."
    curl -L -o dbs_manifest.yaml "${params.dbs_manifest}"
    """
}