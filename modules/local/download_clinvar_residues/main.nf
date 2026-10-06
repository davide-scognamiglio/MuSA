/*
 * MuSA
 * Module: DOWNLOAD_CLINVAR_RESIDUES
 * Purpose: Index ClinVar's pathogenic missense variants by residue, for PS1 and PM5
 *
 * ClinVar's VCF carries no protein change, so the residues come from ClinVar's monthly
 * variant_summary (the archived release closest to the ClinVar VCF in the manifest). Only the
 * index is kept (~0.6 MB, see bin/clinvar_residues.py); the 440 MB summary is deleted once built.
 */


process DOWNLOAD_CLINVAR_RESIDUES {
    tag "clinvar_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('clinvar_residues_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "clinvar_variant_summary" "${changed_entries}" "/data/clinvar_residues"; then
        echo "[INFO] No changes for download_clinvar_residues -- skipping download, reusing existing data."
        cp "${manifest}" clinvar_residues_manifest.yaml
        exit 0
    fi

    mkdir -p clinvar_residues
    cd clinvar_residues

    fetch_entry "\$PWD/../${manifest}" clinvar_variant_summary
    clinvar_residues.py build "\${clinvar_variant_summary_out}" clinvar_residues.tsv.gz
    rm "\${clinvar_variant_summary_out}"

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "clinvar_residues" "/data/clinvar_residues"

    mv ${manifest} clinvar_residues_manifest.yaml
    """
}
