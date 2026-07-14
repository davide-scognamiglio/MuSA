/*
 * MuSA
 * Module: DOWNLOAD_DBSCSNV
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_DBSCSNV {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "dbscSNV"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('dbscsnv_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_dbscsnv" "${changed_entries}" "/data/vep_data/dbscSNV"; then
        echo "[INFO] No changes for download_dbscsnv -- skipping download, reusing existing data."
        cp "${manifest}" dbscsnv_manifest.yaml
        exit 0
    fi

    mkdir -p dbscSNV
    cd dbscSNV

    prefix="vep_dbscsnv"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    # write SHA back into manifest
    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # ---- post-processing ----

    unzip "\${!out_var}"

    head -n1 dbscSNV1.1.chr1 > h

    cat dbscSNV1.1.chr* \
        | grep -v '^chr' \
        | sort -k5,5 -k6,6n \
        | cat h - \
        | awk '\$5 != "."' \
        | bgzip -c > dbscSNV1.1_GRCh38.txt.gz

    tabix -s 5 -b 6 -e 6 -c c dbscSNV1.1_GRCh38.txt.gz

    cd ..

    mv ${manifest} dbscsnv_manifest.yaml
    """
}