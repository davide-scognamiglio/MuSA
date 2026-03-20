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
    container "dsbioinfo/musa-helper:latest"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${maf.baseName}.cleaned.maf")

    script:
    """
    set -euo pipefail

    # Columns to drop outright.
    # For columns that appear more than once (HGVSp, MANE, TSL, APPRIS),
    # the dedup logic below automatically keeps the first occurrence
    # and silently discards every subsequent one.
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
            # Skip if explicitly dropped, or already seen (keep first occurrence only)
            if ((col in drop) || (col in seen)) {
                keep[i] = 0
            } else {
                keep[i] = 1
                seen[col] = 1
            }
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