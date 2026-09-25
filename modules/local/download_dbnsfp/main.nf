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
    path dbnsfp_zip     // user's zip, or the NO_FILE sentinel
    val  dbnsfp_url     // user's download link, or ""

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

    # dbNSFP is distributed only to registered users: the public manifest's url is empty and the
    # user supplies the zip (--dbnsfp_zip) or their own link (--dbnsfp_url). A custom manifest
    # may still carry a url, used last.
    if [[ "\$(basename "${dbnsfp_zip}")" != "NO_FILE" ]]; then
        echo "[INFO] Using the dbNSFP zip given with --dbnsfp_zip" >&2
        sha=\$(sha256sum "${dbnsfp_zip}" | awk '{print \$1}')
        zip_file="${dbnsfp_zip}"
    else
        url="${dbnsfp_url}"
        url="\${url:-\${dbnsfp_url:-}}"
        if [[ -z "\$url" ]]; then
            echo "[ERROR] dbNSFP needs --dbnsfp_url or --dbnsfp_zip (register at https://www.dbnsfp.org/download)" >&2
            exit 1
        fi
        # The link is personal: keep it out of .command.log.
        sha=\$(download_and_compute_sha "\$url" "\$dbnsfp_method" "\$dbnsfp_out" 2> >(sed "s|\$url|<dbNSFP download link>|g" >&2))
        zip_file="\$dbnsfp_out"
    fi
    expected="\${dbnsfp_expected_sha256:-}"
    if [[ -n "\$expected" && "\$sha" != "\$expected" ]]; then
        echo "[ERROR] dbNSFP zip SHA-256 \$sha does not match the manifest (\$expected): is it \$dbnsfp_out?" >&2
        exit 1
    fi
    write_computed_sha256 "${manifest}" "dbnsfp" \$sha

    unzip "\$zip_file"
    [[ "\$zip_file" == "\$dbnsfp_out" ]] && rm "\$dbnsfp_out"

    # Rename whatever versioned folder was extracted to a fixed name
    extracted_dir=\$(basename "\$dbnsfp_out" .zip)
    mv "\$extracted_dir" dbNSFP

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "dbNSFP" "/data/dbNSFP/dbNSFP"

    mv ${manifest} dbnsfp_manifest.yaml
    """
}
