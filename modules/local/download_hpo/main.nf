/*
 * MuSA
 * Module: DOWNLOAD_HPO
 * Purpose: Download the Human Phenotype Ontology and its gene and disease annotations
 *
 * All three files come from one HPO release, through its versioned PURLs, so the ontology and the
 * annotations always agree on term IDs. HPO_MATCH reads them to compare the patient's HPO terms
 * with each gene's.
 */


process DOWNLOAD_HPO {
    tag "hpo_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('hpo_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "hpo hpo_genes_to_phenotype hpo_phenotype_hpoa" "${changed_entries}" "/data/hpo"; then
        echo "[INFO] No changes for download_hpo -- skipping download, reusing existing data."
        cp "${manifest}" hpo_manifest.yaml
        exit 0
    fi

    mkdir -p hpo
    cd hpo

    for var_prefix in hpo hpo_genes_to_phenotype hpo_phenotype_hpoa; do
        url_var="\${var_prefix}_url"
        method_var="\${var_prefix}_method"
        out_var="\${var_prefix}_out"
        expected_var="\${var_prefix}_expected_sha256"

        if [ -z "\${!url_var:-}" ]; then
            echo "[ERROR] '\$url_var' is not set. Check your manifest." >&2
            exit 1
        fi

        sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

        # The URLs name a release, so the files cannot legitimately change under them.
        expected="\${!expected_var:-}"
        if [[ -n "\$expected" && "\$sha" != "\$expected" ]]; then
            echo "[ERROR] \${!out_var}: SHA-256 \$sha does not match the manifest (\$expected)" >&2
            exit 1
        fi

        write_computed_sha256 "../${manifest}" "\${var_prefix}" "\$sha"
    done

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "hpo" "/data/hpo"

    mv ${manifest} hpo_manifest.yaml
    """
}
