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
    container "dsbioinfo/musa-helper:rebuild"

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
        print "0_KEY", \$0
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
        for (i=1; i<=NF; i++) {
            # dbNSFP MANE is the per-transcript array (".;.;Select;."); VEP MANE, already in this
            # merge, is a single flag for the one transcript VEP picked. Same column name, different
            # meaning - and CLEAN_COLUMNS keeps only the first of two same-named columns, which
            # silently dropped the array: the only thing that says which array position is the
            # canonical isoform. Rename it so both survive.
            if (\$i == "MANE") \$i = "MANE_dbNSFP"
            hdr[\$i] = i
        }
        print "0_KEY", \$0
        next
    }
    {
        gsub(/\r/, "")
        key = ""
        for (i=1; i<=length(kc); i++) key = key (i>1 ? "|" : "") \$(hdr[kc[i]])
        print key, \$0
    }
    ' "\$DBS_IN" | sort -t\$'\\t' -k1,1 > "\$DBS_NORM"

    # --- 2b. Collapse dbNSFP to ONE row per key, keeping the isoform VEP actually picked ---
    #
    # dbNSFP stores one row per distinct amino-acid consequence, so a variant in a gene whose
    # isoforms disagree on reading frame over that position yields SEVERAL rows sharing the same
    # CHROM|POS|REF|ALT key (e.g. chr10:98430667 G>C in HPS1: one row H/Q, one row T/R).
    # A plain join on a non-unique key then emits a cartesian product: the MAF row is duplicated,
    # and one copy carries predictor scores (REVEL, SIFT, PolyPhen, MetaRNN, ...) taken from an
    # isoform that VEP did not select. Downstream consumers key on the variant, so the surviving
    # row - and therefore the in-silico evidence - would be decided arbitrarily.
    #
    # Keep the dbNSFP row whose Ensembl_transcriptid list contains the transcript VEP picked
    # (Feature). Fall back to the row with the most populated fields when no list matches.
    DBS_DEDUP="dbnsfp.dedup.tsv"
    awk -F'\t' -v OFS='\t' '
    NR==FNR {
        if (FNR==1) { for (i=1; i<=NF; i++) vh[\$i] = i; next }
        feat[\$1] = \$(vh["Feature"])
        next
    }
    FNR==1 {
        for (i=1; i<=NF; i++) dh[\$i] = i
        tid = dh["Ensembl_transcriptid"]
        print
        next
    }
    {
        k = \$1
        s = 0
        if (tid > 0 && feat[k] != "" && index(\$(tid), feat[k]) > 0) s = 1000000
        pop = 0
        for (i=2; i<=NF; i++) if (\$i != "." && \$i != "" && \$i != "NA") pop++
        s += pop
        if (!(k in bscore) || s > bscore[k]) { bscore[k] = s; brow[k] = \$0 }
    }
    END { for (k in brow) print brow[k] }
    ' "\$VEP_NORM" "\$DBS_NORM" | sort -t\$'\\t' -k1,1 > "\$DBS_DEDUP"

    # --- 2c. Collapse dbNSFP's per-transcript arrays to the MANE transcript (params-controlled) ---
    #
    # Dedup above settles WHICH ROW survives; this settles which element INSIDE that row's arrays is
    # the answer. dbNSFP keeps transcript-specific fields as ';'-delimited arrays aligned with
    # Ensembl_transcriptid, so "SIFT_score = .;0.169;0.169;." is unreadable on its own: the position of
    # the canonical isoform lives in MANE_dbNSFP (".;.;Select;.") and nowhere else. Ensembl_transcriptid
    # names the transcript at each position but does not mark which one is MANE.
    #   mane (default) - rewrite each transcript-aligned column to the element at MANE_dbNSFP's Select
    #   all            - leave the arrays alone; MANE_dbNSFP is what indexes them
    # Which columns are transcript-aligned comes from a fixed, committed list rather than from probing
    # this file, so the same column is collapsed for every patient: dbNSFP also uses ';' for gene-level
    # fields (GO_*, Pathway(*), HPO_*, ...) that must never be indexed by a transcript position, and a
    # per-file guess would vary with whichever rows a patient happens to have. Regenerate the list on a
    # dbNSFP upgrade with bin/gen_dbnsfp_aligned_columns.py.
    DBS_FINAL="\$DBS_DEDUP"
    case "${params.dbnsfp_transcript_scores}" in
        mane)
            dbnsfp_collapse_mane.py "\$DBS_DEDUP" "dbnsfp.mane.tsv" \\
                "${projectDir}/assets/dbnsfp_transcript_aligned_columns.txt" "\$VEP_NORM"
            DBS_FINAL="dbnsfp.mane.tsv"
            ;;
        all) ;;
        *)
            echo "ERROR: --dbnsfp_transcript_scores must be 'mane' or 'all' (got '${params.dbnsfp_transcript_scores}')" >&2
            exit 1
            ;;
    esac

    # --- 3. Normalize Renovo  (key: Otherinfo4 | Otherinfo5 | Otherinfo7 | Otherinfo8) ---
    #        Otherinfo4=CHROM, Otherinfo5=POS, Otherinfo7=REF, Otherinfo8=ALT
    RENOVO_NORM="renovo.norm.tsv"
    awk -F'\t' -v OFS='\t' -v key_cols="Otherinfo4 Otherinfo5 Otherinfo7 Otherinfo8" '
    BEGIN { split(key_cols, kc, " ") }
    NR==1 {
        for (i=1; i<=NF; i++) hdr[\$i] = i
        print "0_KEY", \$0
        next
    }
    {
        gsub(/\r/, "")
        key = ""
        for (i=1; i<=length(kc); i++) key = key (i>1 ? "|" : "") \$(hdr[kc[i]])
        print key, \$0
    }
    ' "\$RENOVO_IN" | sort -t\$'\\t' -k1,1 > "\$RENOVO_NORM"

    # --- 4. Normalize MAF  (key: Chromosome | vcf_pos | vcf_ref | vcf_alt) ---
    MAF_NORM="maf.norm.tsv"
    awk -F'\t' -v OFS='\t' -v key_cols="Chromosome vcf_pos vcf_ref vcf_alt" '
    BEGIN { split(key_cols, kc, " ") }
    NR==1 {
        for (i=1; i<=NF; i++) hdr[\$i] = i
        print "0_KEY", \$0
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
    join -t \$'\\t' -1 1 -2 1 -a 1 -e "NA" -o auto "\$VEP_NORM"    "\$DBS_FINAL"  \\
        | join -t \$'\\t' -1 1 -2 1 -a 1 -e "NA" -o auto - "\$RENOVO_NORM" \\
        | join -t \$'\\t' -1 1 -2 1 -a 1 -e "NA" -o auto - "\$MAF_NORM"    \\
        | cut -f2- > "\$OUT"
    """
}