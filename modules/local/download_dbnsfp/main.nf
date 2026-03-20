/*
 * MuSA
 * Module: DOWNLOAD_DBNSFP
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_DBNSFP {
    tag "dbNSFP_setup"
    publishDir "${params.data_dir}/dbNSFP", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"

    output:
    path "dbNSFP5.3.1a"

    script:
    """
    set -euo pipefail

    BASE_URL="https://dist.genos.us/academic/e55b09/"
    TOLERANCE=0.1
    METHOD="wget"

    FILES=(
        "dbNSFP5.3.1a.zip"
    )

    for f in "\${FILES[@]}"; do
        FULL_URL="\$BASE_URL/\$f"
        OUT=\$(basename "\$FULL_URL")
        bash download_and_check.sh "\$FULL_URL" \$TOLERANCE \$METHOD \$OUT
        unzip \$f
        rm \$f
    done
    """
}
