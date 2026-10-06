/*
 * MuSA
 * Module: DOWNLOAD_FLAGLRG
 * Purpose: LRG reference sequences for transcripts (VEP plugin FlagLRG)
 *
 * Maps RefSeq and Ensembl transcripts to their Locus Reference Genomic record, the stable
 * reference clinical reports cite. Published as a current list only, so not checksum-pinned.
 */


process DOWNLOAD_FLAGLRG {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('flaglrg_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_flaglrg" "${changed_entries}" "/data/vep_data/FlagLRG"; then
        echo "[INFO] No changes for download_flaglrg -- skipping download, reusing existing data."
        cp "${manifest}" flaglrg_manifest.yaml
        exit 0
    fi

    mkdir -p FlagLRG
    cd FlagLRG

    for key in vep_flaglrg; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "FlagLRG" "/data/vep_data/FlagLRG"

    mv ${manifest} flaglrg_manifest.yaml
    """
}
