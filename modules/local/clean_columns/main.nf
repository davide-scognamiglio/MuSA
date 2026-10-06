/*
 * MuSA
 * Module: CLEAN_COLUMNS
 * Purpose: Drop duplicate columns and clean the file a little bit
 */

process CLEAN_COLUMNS {
    tag "${meta.patient}"
        cpus params.n_core
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

    # Columns to drop — organised by redundancy tier
    #
    # Original pre-merge VEP fields (may exist in upstream VEP-only MAFs)
    ORIG="CHROM,VEP_canonical,REF,ALT,Ensembl_geneid,POS,ID,Allele,HGVSp,TSL,APPRIS"
    #
    # TIER 1 — identical content, very similar name (keep the higher-coverage twin)
    #   CADD_phred      -> keep CADD_PHRED       (VEP plugin has 2.4x more coverage)
    #   CADD_raw        -> keep CADD_RAW
    #   clinvar_clnsig  -> keep CLNSIG            (dbNSFP's copy; CLNSIG is MuSA's own ClinVar release)
    #   clinvar_review  -> keep CLNREVSTAT
    #   clinvar_trait   -> keep CLNDN
    #   Start           -> keep Start_Position    (MAF standard)
    #   pos(1-based)    -> keep Start_Position    (dbNSFP partial field)
    #   vcf_pos         -> keep Start_Position    (VCF coord, indel offset differs)
    #   End             -> keep End_Position      (MAF standard)
    #   Ref             -> keep Reference_Allele  (MAF standard)
    #   Alt             -> keep Tumor_Seq_Allele2 (MAF standard)
    #   ref             -> keep vcf_ref           (dbNSFP partial field)
    #   alt             -> keep vcf_alt           (dbNSFP partial field)
    #   vcf_qual        -> keep QUAL              (exact duplicate)
    #   MIM_id          -> keep OMIM_id           (same database, side-by-side)
    #   HGVSp_snpEff    -> keep HGVSp_VEP        (identical content, keep VEP)
    T1="CADD_phred,CADD_raw,clinvar_clnsig,clinvar_review,clinvar_trait,Start,pos(1-based),vcf_pos,End,Ref,Alt,ref,alt,vcf_qual,MIM_id,HGVSp_snpEff"
    #
    # TIER 2 — same underlying data, different tool/format/transcript scope
    #   CLIN_SIG           -> keep CLNSIG            (case-only diff: benign vs Benign)
    #   #CHROM             -> keep Chromosome        (VCF header field, partially filled)
    #   #chr               -> keep Chromosome        (dbNSFP field, no chr-prefix)
    #   HGVSc_VEP          -> keep HGVSc             (dbNSFP bare notation vs VEP canonical)
    #   Ensembl_proteinid  -> keep ENSP              (same)
    #   Uniprot_acc        -> keep SWISSPROT         (dbNSFP multi-isoform vs VEP versioned)
    #   genename           -> keep Hugo_Symbol       (dbNSFP duplicates per transcript)
    #   CCDS_id            -> keep CCDS              (dbNSFP bare id vs VEP versioned)
    #   STRAND_VEP         -> keep STRAND            (completely empty column)
    #   cds_strand         -> keep STRAND            (same info, different encoding +/- vs 1/-1)
    #   Uniprot_id         -> keep Uniprot_entry     (single vs multi-transcript mnemonic)
    #   am_class           -> merged into AlphaMissense_pred, then dropped (see below)
    #   am_pathogenicity   -> merged into AlphaMissense_score, then dropped (see below)
    T2="CLIN_SIG,#CHROM,#chr,HGVSc_VEP,Ensembl_proteinid,Uniprot_acc,genename,CCDS_id,STRAND_VEP,cds_strand,am_class,am_pathogenicity,Uniprot_id"
    #
    # KEPT ON PURPOSE:
    #   MANE_dbNSFP          — dbNSFP's per-transcript MANE array (renamed in MERGE_ANNOTATIONS to
    #                          clear the name clash with VEP's single-value MANE). This is the column
    #                          that carries the POSITION of the canonical isoform: the offset of
    #                          "Select" in ".;.;Select;." is the offset to read in every other
    #                          transcript-aligned array. Nothing else in the MAF encodes it, which is
    #                          why losing it to the name clash made the score arrays unreadable.
    #                          After a =mane collapse, '.' here means the scores on that row are NOT
    #                          from a MANE transcript, so it doubles as the provenance flag.
    #   Feature              — VEP's picked transcript. The HGVSc/HGVSp/Consequence on the row are
    #                          expressed against it, and it is the only transcript column populated
    #                          on every row. Never drop it.
    #   Ensembl_transcriptid — the parallel list of transcript IDs. It does NOT say which position is
    #                          MANE (that is MANE_dbNSFP alone); it says which transcript each
    #                          position IS. Kept purely as provenance — under =mane it names the one
    #                          isoform the scores came from, which Feature cannot: Feature is VEP's
    #                          pick, i.e. the most-severe consequence, not necessarily the MANE.
    #
    # DEAD — zero coverage in this file (MAF-standard fields never populated by pipeline)
    DEAD="gnomad_exomes_af,gnomad_genomes_af,Exon_Number,Entrez_Gene_Id,HGVSp_Short"

    DROP="\${ORIG},\${T1},\${T2},\${DEAD}"

    # Dropped by ORIGINAL header name (checked BEFORE the ClinVar_* -> canonical rename below): the
    # bare custom ClinVar id column. The self-managed ClinVar VCF (VEP --custom: ClinVar_CLNSIG/
    # CLNREVSTAT/CLNDN) is the single ClinVar source.
    DROP_ORIG="ClinVar"

    # The protein change: HGVSp_VEP comes from dbNSFP (read on the MANE transcript), and VEP's own
    # HGVSp is dropped above as its pre-merge twin. Basic mode has no dbNSFP, so there VEP's HGVSp
    # (for the transcript VEP picked, Feature) becomes HGVSp_VEP, in dbNSFP's form: "p.Tyr414Cys"
    # rather than "ENSP00000448059.1:p.Tyr414Cys", and "p.Leu385=" rather than VEP's URL-escaped
    # "p.Leu385%3D".

    # UTRAnnotator writes 5UTR_annotation as key=value pairs in Perl hash order, which changes from
    # run to run ("type=uORF:KozakContext=..." one time, "KozakContext=...:type=uORF" the next), so
    # two runs of the same VCF differed. The pairs are sorted by key, inside each '&'-joined item.

    # AlphaMissense has two copies: dbNSFP's (per transcript, read on the MANE transcript) and the
    # VEP plugin's (extended mode; DeepMind's canonical-transcript file, matched by position). They
    # agree where both exist (median difference 0.004 on NA12878), but on ~6% of missense variants
    # only the plugin has a value, because dbNSFP has none for the MANE transcript. dbNSFP's value
    # is kept; an empty one is filled from the plugin (am_class mapped to dbNSFP's LB/A/LP codes),
    # and AlphaMissense_source, written after AlphaMissense_pred, says which copy each row holds.

    awk -F'\\t' -v OFS='\\t' -v drop_cols="\$DROP" -v drop_orig_cols="\$DROP_ORIG" '
    BEGIN {
        n = split(drop_cols, arr, ",")
        for (i = 1; i <= n; i++) drop[arr[i]] = 1
        m = split(drop_orig_cols, arr2, ",")
        for (i = 1; i <= m; i++) drop_orig[arr2[i]] = 1
    }
    function empty(v) { return v == "" || v == "." || v == "NA" || v == "nan" }
    function sort_pairs(v,   items, n, i, out, pairs, m, j, k, t) {
        n = split(v, items, "&")
        out = ""
        for (i = 1; i <= n; i++) {
            m = split(items[i], pairs, ":")
            for (j = 2; j <= m; j++) {
                t = pairs[j]
                for (k = j - 1; k >= 1 && pairs[k] > t; k--) pairs[k + 1] = pairs[k]
                pairs[k + 1] = t
            }
            t = pairs[1]
            for (j = 2; j <= m; j++) t = t ":" pairs[j]
            out = out (i > 1 ? "&" : "") t
        }
        return out
    }
    NR == 1 {
        for (i = 1; i <= NF; i++) {
            name = \$i
            gsub(/\r/, "", name)
            if (name == "AlphaMissense_score" && !am_score) am_score = i
            if (name == "AlphaMissense_pred"  && !am_pred)  am_pred  = i
            if (name == "am_pathogenicity"    && !am_vep)   am_vep   = i
            if (name == "am_class"            && !am_cls)   am_cls   = i
            if (name == "HGVSp"               && !vep_p)    vep_p    = i
            if (name == "HGVSp_VEP")                        dbnsfp_p = i
            if (name == "5UTR_annotation")                  utr5     = i
        }
        if (dbnsfp_p) vep_p = 0
        am_after = am_pred ? am_pred : am_score
        am_code["likely_benign"] = "LB"; am_code["ambiguous"] = "A"; am_code["likely_pathogenic"] = "LP"
        for (i = 1; i <= NF; i++) {
            col = \$i
            gsub(/\r/, "", col)

            # Drop by ORIGINAL name first, so the bare ClinVar id column goes before the custom
            # ClinVar_* fields are renamed to their canonical names just below.
            if (col in drop_orig) {
                keep[i] = 0
                \$i = col
                continue
            }

            # Rename to canonical MAF names
            if (i == vep_p)                            col = "HGVSp_VEP"
            else if (col == "SYMBOL")                  col = "Hugo_Symbol"
            else if (col == "ClinVar_CLNSIG")          col = "CLNSIG"
            else if (col == "ClinVar_CLNREVSTAT")      col = "CLNREVSTAT"
            else if (col == "ClinVar_CLNDN")           col = "CLNDN"
            else if (col == "ClinVar_CLNSIGCONF")      col = "CLNSIGCONF"
            else if (col == "ClinVar_CLNDISDB")        col = "CLNDISDB"
            else if (col == "ClinVar_CLNHGVS")         col = "CLNHGVS"
            else if (col == "ClinVar_MC")              col = "MC"
            else if (col == "ClinVar_GENEINFO")        col = "GENEINFO"
            else if (col == "ClinVar_ALLELEID")        col = "ALLELEID"
            else if (col == "ClinGenVCEP_Assertion")     col = "ClinGen_Variant_Assertion"
            else if (col == "ClinGenVCEP_EvidenceCodes") col = "ClinGen_Variant_EvidenceCodes"
            else if (col == "ClinGenVCEP_Disease")       col = "ClinGen_Variant_Disease"

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
        if (utr5 && NR > 1 && !empty(\$utr5)) \$utr5 = sort_pairs(\$utr5)
        if (vep_p && NR > 1) {
            p = \$vep_p
            sub(/^[^:]*:/, "", p)
            gsub(/%3D/, "=", p)
            \$vep_p = p
        }
        if (am_after) {
            if (NR == 1) {
                am_src = "AlphaMissense_source"
            } else if (!empty(\$am_score)) {
                am_src = "dbNSFP"
            } else if (am_vep && !empty(\$am_vep)) {
                \$am_score = \$am_vep
                if (am_pred) \$am_pred = (\$am_cls in am_code) ? am_code[\$am_cls] : "."
                am_src = "VEP plugin"
            } else {
                am_src = "."
            }
        }
        out = ""
        sep = ""
        for (i = 1; i <= NF; i++) {
            if (keep[i]) {
                out = out sep \$i
                sep = OFS
            }
            if (i == am_after) {
                out = out sep am_src
                sep = OFS
            }
        }
        print out
    }
    ' "${maf}" > "${maf.baseName}.cleaned.maf"
    """
}
