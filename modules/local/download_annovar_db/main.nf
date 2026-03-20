/*
 * MuSA
 * Module: DOWNLOAD_ANNOVAR_DB
 * Purpose: Download ANNOVAR databases
 */


process DOWNLOAD_ANNOVAR_DB{
    tag "renovo_setup"
    publishDir "${params.data_dir}", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"

    output:
    path "renovo_humandb"

    script:
    """
      set -euo pipefail

    mkdir -p renovo_humandb
    cd renovo_humandb

    BASE_URL="http://www.openbioinformatics.org/annovar/download"

    BUILD="${params.build}"
    TOLERANCE=0.1   # 10% size tolerance
    METHOD="wget"

    FILES=(
        "\${BUILD}_refGene.txt.gz"
        "\${BUILD}_refGeneMrna.fa.gz"
        "\${BUILD}_refGeneVersion.txt.gz"
        "\${BUILD}_ensGene.txt.gz"
        "\${BUILD}_ensGeneMrna.fa.gz"
        "\${BUILD}_avsnp150.txt.gz"
        "\${BUILD}_avsnp150.txt.idx.gz"
        "\${BUILD}_gnomad211_exome.txt.gz"
        "\${BUILD}_gnomad211_exome.txt.idx.gz"
        "\${BUILD}_dbnsfp35c.txt.gz"
        "\${BUILD}_dbnsfp35c.txt.idx.gz"
        "\${BUILD}_intervar_20180118.txt.gz"
        "\${BUILD}_intervar_20180118.txt.idx.gz"
        "\${BUILD}_clinvar_20250721.txt.gz"
        "\${BUILD}_clinvar_20250721.txt.idx.gz"
    )

    for f in "\${FILES[@]}"; do
        FULL_URL="\$BASE_URL/\$f"
        OUT=\$(basename "\$FULL_URL")
        bash download_and_check.sh "\$FULL_URL" \$TOLERANCE \$METHOD \$OUT
    done

    gunzip -f *.gz

    cd ..
    """    
}