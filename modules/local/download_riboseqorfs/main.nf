/*
 * MuSA
 * Module: DOWNLOAD_RIBOSEQORFS
 * Purpose: GENCODE Ribo-seq ORF catalogue (VEP plugin RiboseqORFs)
 *
 * Translated ORFs outside the annotated CDS (uORFs, lncRNA ORFs); the plugin re-computes the
 * consequence of variants inside them.
 */


process DOWNLOAD_RIBOSEQORFS {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('riboseqorfs_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_riboseqorfs vep_riboseqorfs_tbi" "${changed_entries}" "/data/vep_data/RiboseqORFs"; then
        echo "[INFO] No changes for download_riboseqorfs -- skipping download, reusing existing data."
        cp "${manifest}" riboseqorfs_manifest.yaml
        exit 0
    fi

    mkdir -p RiboseqORFs
    cd RiboseqORFs

    for key in vep_riboseqorfs vep_riboseqorfs_tbi; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "RiboseqORFs" "/data/vep_data/RiboseqORFs"

    mv ${manifest} riboseqorfs_manifest.yaml
    """
}
