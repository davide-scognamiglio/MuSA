/*
 * MuSA
 * Module: CLEAN_COLUMNS
 * Purpose: Drop duplicate columns and clean the file a little bit
 */

process CLEAN_COLUMNS {
    tag "clean-maf"
    cpus 1
    memory { 18.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${maf.baseName}.cleaned.maf")

    script:
    """
    set -euo pipefail

    # Columns to drop outright (except Hugo_Symbol)
    DROP="CHROM,VEP_canonical,REF,ALT,Ensembl_geneid,POS,ID,Allele,HGVSp,TSL,APPRIS"

    awk -F'\\t' -v OFS='\\t' -v drop_cols="\$DROP" '
    BEGIN {
        n = split(drop_cols, arr, ",")
        for (i = 1; i <= n; i++) drop[arr[i]] = 1
    }
    NR == 1 {
        for (i = 1; i <= NF; i++) {
            col = \$i
            gsub(/\r/, "", col)

            # Rename SYMBOL -> Hugo_Symbol
            if (col == "SYMBOL") {
                col = "Hugo_Symbol"
            }

            # Skip if explicitly dropped or already seen (keep first occurrence only)
            if ((col in drop) || (col in seen)) {
                keep[i] = 0
            } else {
                keep[i] = 1
                seen[col] = 1
            }

            \$i = col
        }
    }
    {
        gsub(/\r/, "")
        out = ""
        sep = ""
        for (i = 1; i <= NF; i++) {
            if (keep[i]) {
                out = out sep \$i
                sep = OFS
            }
        }
        print out
    }
    ' "${maf}" > "${maf.baseName}.cleaned.maf"
    """
}