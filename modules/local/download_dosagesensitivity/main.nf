/*
 * MuSA
 * Module: DOWNLOAD_DOSAGESENSITIVITY
 * Purpose: Collins 2022 dosage sensitivity scores (VEP plugin DosageSensitivity)
 *
 * pHaplo and pTriplo for ~18,600 genes, from rare CNVs in ~950,000 people. ClinGen's curated
 * dosage covers ~1,500 genes; these are model probabilities for nearly all of them.
 */


process DOWNLOAD_DOSAGESENSITIVITY {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('dosagesensitivity_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_dosagesensitivity" "${changed_entries}" "/data/vep_data/DosageSensitivity"; then
        echo "[INFO] No changes for download_dosagesensitivity -- skipping download, reusing existing data."
        cp "${manifest}" dosagesensitivity_manifest.yaml
        exit 0
    fi

    mkdir -p DosageSensitivity
    cd DosageSensitivity

    for key in vep_dosagesensitivity; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "DosageSensitivity" "/data/vep_data/DosageSensitivity"

    mv ${manifest} dosagesensitivity_manifest.yaml
    """
}
