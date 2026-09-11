/*
 * MuSA
 * Module: DOWNLOAD_DBNSFP
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_DBNSFP {
    tag "dbNSFP_setup"
    publishDir "${params.data_dir}/dbNSFP", mode: 'copy', overwrite: true, pattern: "dbNSFP"
    container "dsbioinfo/musa-helper:rebuild"

    input:
    file manifest
    path changed_entries

    output:
        file('dbnsfp_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh
    parse_manifest "${manifest}"

    if should_skip_module "dbnsfp" "${changed_entries}" "/data/dbNSFP/dbNSFP"; then
        echo "[INFO] No changes for download_dbnsfp -- skipping download, reusing existing data."
        cp "${manifest}" dbnsfp_manifest.yaml
        exit 0
    fi

    sha=\$(download_and_compute_sha "\$dbnsfp_url" "\$dbnsfp_method" "\$dbnsfp_out")
    write_computed_sha256 "${manifest}" "dbnsfp" \$sha

    unzip \$dbnsfp_out
    rm \$dbnsfp_out

    # Rename whatever versioned folder was extracted to a fixed name
    extracted_dir=\$(basename "\$dbnsfp_out" .zip)
    mv "\$extracted_dir" dbNSFP

    mv ${manifest} dbnsfp_manifest.yaml
    """
}
