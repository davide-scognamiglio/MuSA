/*
 * MuSA
 * Module: DOWNLOAD_SPLICEVAULT
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_SPLICEVAULT {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "SpliceVault"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("SpliceVault"),file('splicevault_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p SpliceVault
    cd SpliceVault

    prefix="vep_splicevault"

    # -------------------------------------------------------
    # bare entry has no infix:  vep_splicevault_url
    # tbi entry has infix:      vep_splicevault_tbi_url
    # -------------------------------------------------------
    for suffix in "" "tbi"; do

        if [ -z "\$suffix" ]; then
            var_prefix="\${prefix}"
            label="main"
        else
            var_prefix="\${prefix}_\${suffix}"
            label="\$suffix"
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

    cd ..

    mv "${manifest}" splicevault_manifest.yaml
    """
}