/*
 * MuSA
 * Module: DOWNLOAD_VEP_CACHE
 * Purpose: Download VEP cache
 */


process DOWNLOAD_VEP_CACHE {
    tag "vep_setup"
    publishDir "${params.data_dir}", mode: 'copy', overwrite: true, pattern: "vep_data/vep_cache/homo_sapiens"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("vep_data/vep_cache/homo_sapiens"),file('vep_cache_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh
    parse_manifest "${manifest}"

    mkdir -p vep_data/vep_cache
    cd vep_data/vep_cache
    echo "Downloading VEP cache for homo_sapiens GRCh38..."
    
    sha=\$(download_and_compute_sha "\$vep_cache_url" "\$vep_cache_method" "\$vep_cache_out")
    write_computed_sha256 "../../${manifest}" "vep_cache" \$sha

    tar xzf \$vep_cache_out   

    cd ../../

    mv ${manifest} vep_cache_manifest.yaml

    """
}