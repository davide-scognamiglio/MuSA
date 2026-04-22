/*
 * MuSA
 * Module: DOWNLOAD_CLINPRED
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_CLINPRED {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "ClinPred"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path('ClinPred'),file('clinpred_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p ClinPred
    cd ClinPred

    prefix="vep_clinpred"

    url_var="\${prefix}_url"        # here: Google Drive file ID
    method_var="\${prefix}_method"  # should be 'gdown'
    out_var="\${prefix}_out"

    echo "[INFO] Processing \$prefix"

    sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

    # Write SHA back into manifest
    write_computed_sha256 "../${manifest}" "\$prefix" "\$sha"

    echo "[INFO] \$prefix hash written"

    # --- Post-processing ---
    awk '(\$2 == "Start" || \$2 ~ /^[0-9]+\$/){print \$0}' "\${!out_var}" > ClinPred_${params.build}_tabbed.tsv

    sed -i '1s/.*/#&/' ClinPred_${params.build}_tabbed.tsv
    sed -i '1s/Chr/chr/' ClinPred_${params.build}_tabbed.tsv

    { 
        head -n1 ClinPred_${params.build}_tabbed.tsv
        tail -n +2 ClinPred_${params.build}_tabbed.tsv | sort -k1,1V -k2,2V
    } > ClinPred_${params.build}_sorted_tabbed.tsv

    bgzip ClinPred_${params.build}_sorted_tabbed.tsv
    tabix -f -s 1 -b 2 -e 2 ClinPred_${params.build}_sorted_tabbed.tsv.gz

    cd ..

    # Emit updated manifest
    mv ${manifest} clinpred_manifest.yaml
    """
}