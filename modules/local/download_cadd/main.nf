/*
 * MuSA
 * Module: DOWNLOAD_CADD
 * Purpose: Download the CADD plugin's precomputed scores
 *
 * Two score files, each with its index: every possible SNV, and the indels seen in gnomAD v4
 * genomes (CADD has no precomputed score for any other indel). Under --update_db_only an unchanged
 * entry already installed is reused rather than downloaded again (reuse_installed).
 */


process DOWNLOAD_CADD {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('cadd_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    _keys=""
    for var in \$(compgen -v); do
        if [[ \$var =~ ^vep_cadd_.*_url\$ ]]; then
            _keys="\$_keys \${var%_url}"
        fi
    done

    if should_skip_module "\$_keys" "${changed_entries}" "/data/vep_data/CADD"; then
        echo "[INFO] No changes for download_cadd -- skipping download, reusing existing data."
        cp "${manifest}" cadd_manifest.yaml
        exit 0
    fi

    mkdir -p CADD
    reused=0

    # Loop over CADD entries defined in manifest
    for var in \$(compgen -v); do
        if [[ \$var =~ ^vep_cadd_.*_url\$ ]]; then
            prefix="\${var%_url}"

            out_var="\${prefix}_out"

            echo "[INFO] Processing \$prefix"

            if sha=\$(reuse_installed "\$prefix" "${changed_entries}" "/data/vep_data/CADD/\${!out_var}"); then
                reused=1
                write_computed_sha256 "${manifest}" "\$prefix" "\$sha"
            else
                (cd CADD && fetch_entry "\$PWD/../${manifest}" "\$prefix")
            fi
        fi
    done

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir. With reused files, only the new
    # downloads are moved in, next to them.
    if [[ "\$reused" == 1 ]]; then
        install_files_into_data "CADD" "/data/vep_data/CADD"
    else
        install_into_data "CADD" "/data/vep_data/CADD"
    fi

    mv ${manifest} cadd_manifest.yaml
    """
}