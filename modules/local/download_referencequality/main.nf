/*
 * MuSA
 * Module: DOWNLOAD_REFERENCEQUALITY
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_REFERENCEQUALITY {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "ReferenceQuality"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("ReferenceQuality"),file('referencequality_manifest.yaml')

script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p ReferenceQuality
    cd ReferenceQuality

    prefix="vep_referencequality"

    # ----------------------------------------------------
    # assembly entry has no infix:  vep_referencequality_url
    # issues entry has infix:       vep_referencequality_issues_url
    # ----------------------------------------------------
    for part in "" "issues"; do

        if [ -z "\$part" ]; then
            var_prefix="\${prefix}"
            label="assembly"
        else
            var_prefix="\${prefix}_\${part}"
            label="\$part"
        fi

        url_var="\${var_prefix}_url"
        method_var="\${var_prefix}_method"
        out_var="\${var_prefix}_out"

        echo "[INFO] Processing \${prefix} - \${label} (looking up \$url_var)"

        if [ -z "\${!url_var+x}" ]; then
            echo "[ERROR] Variable '\$url_var' is not set. Check your manifest." >&2
            exit 1
        fi

        sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

        write_computed_sha256 "../${manifest}" "\${var_prefix}" "\$sha"

        echo "[INFO] \${var_prefix} hash written"
    done

    # ----------------------------------------------------
    # Post-processing
    # ----------------------------------------------------
    cat "\${vep_referencequality_out}" "\${vep_referencequality_issues_out}" \
            > GRCh38_quality_mergedfile.gff3

    sort -k1,1 -k4,4n -k5,5n GRCh38_quality_mergedfile.gff3 \
        > sorted_GRCh38_quality_mergedfile.gff3

    bgzip sorted_GRCh38_quality_mergedfile.gff3
    tabix -p gff sorted_GRCh38_quality_mergedfile.gff3.gz

    cd ..

    mv ${manifest} referencequality_manifest.yaml
    """
}