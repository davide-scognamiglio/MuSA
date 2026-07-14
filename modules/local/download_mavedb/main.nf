/*
 * MuSA
 * Module: DOWNLOAD_MAVEDB
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_MAVEDB {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "MaveDB"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('mavedb_manifest.yaml')

 script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_mavedb vep_mavedb_tbi" "${changed_entries}" "/data/vep_data/MaveDB"; then
        echo "[INFO] No changes for download_mavedb -- skipping download, reusing existing data."
        cp "${manifest}" mavedb_manifest.yaml
        exit 0
    fi

    mkdir -p MaveDB
    cd MaveDB

    prefix="vep_mavedb"

    # ---------------------------------------
    # vcf entry has no infix:  vep_mavedb_url
    # tbi entry has infix:     vep_mavedb_tbi_url
    # ---------------------------------------
    for suffix in "" "tbi"; do

        if [ -z "\$suffix" ]; then
            var_prefix="\${prefix}"
            label="vcf"
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

    mv ${manifest} mavedb_manifest.yaml
    """
}