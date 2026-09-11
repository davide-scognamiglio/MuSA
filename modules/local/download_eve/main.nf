/*
 * MuSA
 * Module: DOWNLOAD_EVE
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_EVE {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "EVE"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('eve_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_eve" "${changed_entries}" "/data/vep_data/EVE"; then
        echo "[INFO] No changes for download_eve -- skipping download, reusing existing data."
        cp "${manifest}" eve_manifest.yaml
        exit 0
    fi

    mkdir -p EVE
    cd EVE

    prefix="vep_eve"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # ----------------------------
    # Post-processing
    # ----------------------------

    unzip "\${!out_var}" -d download/

    DATA_FOLDER="download/vcf_files_missense_mutations/"
    OUTPUT_NAME="eve_merged.vcf"

    cat \$(ls "\$DATA_FOLDER"/*vcf | head -n1) > header

    ls "\$DATA_FOLDER"/*vcf | while read VCF; do
        grep -v '^#' "\$VCF" >> variants
    done

    cat header variants \
        | awk '\$1 ~ /^#/ {print \$0; next} {print \$0 | "sort -k1,1V -k2,2n"}' \
        > "\$OUTPUT_NAME"

    rm -f header variants

    bgzip "\$OUTPUT_NAME"
    tabix "\$OUTPUT_NAME.gz"

    rm -rf download download.zip

    cd ..

    mv ${manifest} eve_manifest.yaml
    """
}