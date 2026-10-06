/*
 * MuSA
 * Module: DOWNLOAD_MECHPREDICT
 * Purpose: Predicted disease mechanism per gene (VEP plugin MechPredict)
 *
 * Badonyi et al. 2024: probability that a gene's dominant disease variants act by dominant-negative,
 * gain- or loss-of-function mechanisms. The three published tables are joined into the plugin's
 * input as MechPredict.pm describes.
 */


process DOWNLOAD_MECHPREDICT {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('mechpredict_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_mechpredict_dn vep_mechpredict_gof vep_mechpredict_lof" "${changed_entries}" "/data/vep_data/MechPredict"; then
        echo "[INFO] No changes for download_mechpredict -- skipping download, reusing existing data."
        cp "${manifest}" mechpredict_manifest.yaml
        exit 0
    fi

    mkdir -p MechPredict
    cd MechPredict

    for key in vep_mechpredict_dn vep_mechpredict_gof vep_mechpredict_lof; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    # MechPredict.pm's recipe: key each table by "gene uniprot", join the three, keep one copy of the
    # identifiers and the three probabilities. join needs both inputs sorted in its own collation:
    # LC_ALL=C for both.
    export LC_ALL=C
    for m in pdn pgof plof; do
        cut --complement -f4 "\$m.tsv" | awk '{print \$1 " " \$2 "\\t" \$0}' | sort > "\$m.mod.tsv"
    done
    join -t \$'\\t' -1 1 -2 1 pdn.mod.tsv pgof.mod.tsv \\
        | join -t \$'\\t' -1 1 -2 1 - plof.mod.tsv \\
        | cut --complement -f1,5,6,8,9 \\
        | sed '1i gene\\tuniprot_id\\tpDN\\tpGOF\\tpLOF' > MechPredict_input.tsv
    rm pdn.tsv pgof.tsv plof.tsv pdn.mod.tsv pgof.mod.tsv plof.mod.tsv

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "MechPredict" "/data/vep_data/MechPredict"

    mv ${manifest} mechpredict_manifest.yaml
    """
}
