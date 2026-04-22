/*
 * MuSA
 * Module: DOWNLOAD_GWAS
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_GWAS {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "GWAS"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("GWAS"),file('gwas_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p GWAS
    cd GWAS

    prefix="vep_gwas"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"
 
    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # -------------------------
    # Post-processing
    # -------------------------

    unzip "\${!out_var}"
    rm -f "\${!out_var}"

    cd ..

    mv ${manifest} gwas_manifest.yaml
    """
}