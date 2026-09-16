/*
 * MuSA
 * Module: DOWNLOAD_DBNSFP
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_DBNSFP {
    tag "dbNSFP_setup"
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

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "dbNSFP" "/data/dbNSFP/dbNSFP"

    mv ${manifest} dbnsfp_manifest.yaml
    """
}
