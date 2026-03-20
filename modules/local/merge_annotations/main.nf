/*
 * MuSA
 * Module: MERGE_ANNOTATIONS
 * Purpose: Merge annotations in a single maf file
 */

process MERGE_ANNOTATIONS {
    tag "merge-annotations"
    cpus params.n_core
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 3
    container "dsbioinfo/musa-helper:latest"

    input:
    tuple val(meta), file(vep), file(dbnsfp), file(renovo), file(maf)

    output:
    tuple val(meta), file("${meta.patient}.merged_annotations.tsv")

    script:
    """
    set -euo pipefail
    VEP_IN="${vep}"
    DBS_IN="${dbnsfp}"
    RENOVO_IN="${renovo}"
    MAF_IN="${maf}"
    OUT="${meta.patient}.merged_annotations.tsv"

    # --- 1. Normalize VEP  (key: CHROM | POS | REF | ALT) ---
    VEP_NORM="vep.norm.tsv"
    awk -F'\t' -v OFS='\t' -v key_cols="CHROM POS REF ALT" '
    BEGIN { split(key_cols, kc, " ") }
    NR==1 {
        for (i=1; i<=NF; i++) hdr[\$i] = i
        print "KEY", \$0
        next
    }
    {
        gsub(/\r/, "")
        key = ""
        for (i=1; i<=length(kc); i++) key = key (i>1 ? "|" : "") \$(hdr[kc[i]])
        print key, \$0
    }
    ' "\$VEP_IN" | sort -t\$'\\t' -k1,1 > "\$VEP_NORM"

    # --- 2. Normalize dbNSFP  (key: #CHROM | POS | REF | ALT) ---
    #        Note: header column is literally "#CHROM" (hash included)
    DBS_NORM="dbnsfp.norm.tsv"
    awk -F'\t' -v OFS='\t' -v key_cols="#CHROM POS REF ALT" '
    BEGIN { split(key_cols, kc, " ") }
    NR==1 {
        for (i=1; i<=NF; i++) hdr[\$i] = i
        print "KEY", \$0
        next
    }
    {
        gsub(/\r/, "")
        key = ""
        for (i=1; i<=length(kc); i++) key = key (i>1 ? "|" : "") \$(hdr[kc[i]])
        print key, \$0
    }
    ' "\$DBS_IN" | sort -t\$'\\t' -k1,1 > "\$DBS_NORM"

    # --- 3. Normalize Renovo  (key: Otherinfo4 | Otherinfo5 | Otherinfo7 | Otherinfo8) ---
    #        Otherinfo4=CHROM, Otherinfo5=POS, Otherinfo7=REF, Otherinfo8=ALT
    RENOVO_NORM="renovo.norm.tsv"
    awk -F'\t' -v OFS='\t' -v key_cols="Otherinfo4 Otherinfo5 Otherinfo7 Otherinfo8" '
    BEGIN { split(key_cols, kc, " ") }
    NR==1 {
        for (i=1; i<=NF; i++) hdr[\$i] = i
        print "KEY", \$0
        next
    }
    {
        gsub(/\r/, "")
        key = ""
        for (i=1; i<=length(kc); i++) key = key (i>1 ? "|" : "") \$(hdr[kc[i]])
        print key, \$0
    }
    ' "\$RENOVO_IN" | sort -t\$'\\t' -k1,1 > "\$RENOVO_NORM"

    # --- 4. Normalize MAF  (key: Chromosome | vcf_pos | Reference_Allele | Tumor_Seq_Allele2) ---
    MAF_NORM="maf.norm.tsv"
    awk -F'\t' -v OFS='\t' -v key_cols="Chromosome vcf_pos Reference_Allele Tumor_Seq_Allele2" '
    BEGIN { split(key_cols, kc, " ") }
    NR==1 {
        for (i=1; i<=NF; i++) hdr[\$i] = i
        print "KEY", \$0
        next
    }
    {
        gsub(/\r/, "")
        key = ""
        for (i=1; i<=length(kc); i++) key = key (i>1 ? "|" : "") \$(hdr[kc[i]])
        print key, \$0
    }
    ' "\$MAF_IN" | sort -t\$'\\t' -k1,1 > "\$MAF_NORM"

    # --- 5. Sequential outer-join on KEY, then drop the KEY column ---
    join -t \$'\\t' -1 1 -2 1 -a 1 -e "NA" -o auto "\$VEP_NORM"    "\$DBS_NORM"    \\
        | join -t \$'\\t' -1 1 -2 1 -a 1 -e "NA" -o auto - "\$RENOVO_NORM" \\
        | join -t \$'\\t' -1 1 -2 1 -a 1 -e "NA" -o auto - "\$MAF_NORM"    \\
        | cut -f2- > "\$OUT"
    """
}