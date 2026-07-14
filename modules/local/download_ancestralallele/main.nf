/*
 * MuSA
 * Module: DOWNLOAD_ANCESTRALALLELE
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_ANCESTRALALLELE {
    tag "vep_setup"    
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "AncestralAllele"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('ancestralallele_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_ancestralallele" "${changed_entries}" "/data/vep_data/AncestralAllele"; then
        echo "[INFO] No changes for download_ancestralallele -- skipping download, reusing existing data."
        cp "${manifest}" ancestralallele_manifest.yaml
        exit 0
    fi

    mkdir -p AncestralAllele
    cd AncestralAllele

    prefix="vep_ancestralallele"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    # Write SHA back into manifest
    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # Extract and process
    tar xfz "\${!out_var}"

    bgzip -c homo_sapiens_ancestor_GRCh38/*.fa > homo_sapiens_ancestor_GRCh38.fa.gz

    rm -rf homo_sapiens_ancestor_GRCh38/ "\${!out_var}"

    cd ..

    # Emit updated manifest
    mv ${manifest} ancestralallele_manifest.yaml
    """
}