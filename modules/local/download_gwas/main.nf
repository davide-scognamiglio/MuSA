/*
 * MuSA
 * Module: DOWNLOAD_GWAS
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_GWAS {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('gwas_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_gwas" "${changed_entries}" "/data/vep_data/GWAS"; then
        echo "[INFO] No changes for download_gwas -- skipping download, reusing existing data."
        cp "${manifest}" gwas_manifest.yaml
        exit 0
    fi

    mkdir -p GWAS
    cd GWAS

    prefix="vep_gwas"

    url_var="\${prefix}_url"
    method_var="\${prefix}_method"
    out_var="\${prefix}_out"
 
    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # -------------------------
    # Post-processing
    # -------------------------

    unzip "\${!out_var}"
    rm -f "\${!out_var}"

    # The GWAS Catalog renames the TSV inside this zip between releases (it has shipped
    # ...-v1.0-full.tsv and, as of 2026-09, ...-alt-full.tsv, same columns). VEP_ANNOTATE_VCF opens a
    # fixed name, so install whatever single TSV arrived under that name.
    extracted=( *.tsv )
    if [ \${#extracted[@]} -ne 1 ] || [ ! -f "\${extracted[0]}" ]; then
        echo "[ERROR] expected exactly one .tsv in the GWAS Catalog download, found: \${extracted[*]}" >&2
        exit 1
    fi
    if [ "\${extracted[0]}" != "gwas-catalog-download-associations-v1.0-full.tsv" ]; then
        mv "\${extracted[0]}" gwas-catalog-download-associations-v1.0-full.tsv
    fi

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "GWAS" "/data/vep_data/GWAS"

    mv ${manifest} gwas_manifest.yaml
    """
}