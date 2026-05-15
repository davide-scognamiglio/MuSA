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

    # Columns to drop — organised by redundancy tier
    #
    # Original pre-merge VEP fields (may exist in upstream VEP-only MAFs)
    ORIG="CHROM,VEP_canonical,REF,ALT,Ensembl_geneid,POS,ID,Allele,HGVSp,TSL,APPRIS"
    #
    # TIER 1 — identical content, very similar name (keep the higher-coverage twin)
    #   CADD_phred      -> keep CADD_PHRED       (VEP plugin has 2.4x more coverage)
    #   CADD_raw        -> keep CADD_RAW
    #   clinvar_clnsig  -> keep CLNSIG            (ANNOVAR has 2.6x more coverage)
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
    #   rs_dbSNP        -> keep avsnp150          (ANNOVAR has 2.5x more coverage)
    #   ClinPred        -> keep ClinPred_score    (dbNSFP has more coverage)
    #   HGVSp_snpEff    -> keep HGVSp_VEP        (identical content, keep VEP)
    #   ExonicFunc.ensGene -> keep ExonicFunc.refGene (99.3% match, keep refGene)
    T1="CADD_phred,CADD_raw,clinvar_clnsig,clinvar_review,clinvar_trait,Start,pos(1-based),vcf_pos,End,Ref,Alt,ref,alt,vcf_qual,MIM_id,rs_dbSNP,ClinPred,HGVSp_snpEff,ExonicFunc.ensGene"
    #
    # TIER 2 — same underlying data, different tool/format/transcript scope
    #   CLIN_SIG           -> keep CLNSIG            (case-only diff: benign vs Benign)
    #   Chr                -> keep Chromosome        (ANNOVAR dup of MAF standard)
    #   #CHROM             -> keep Chromosome        (VCF header field, partially filled)
    #   #chr               -> keep Chromosome        (dbNSFP field, no chr-prefix)
    #   HGVSc_VEP          -> keep HGVSc             (dbNSFP bare notation vs VEP canonical)
    #   Ensembl_transcriptid -> keep Feature         (dbNSFP all-transcripts vs VEP canonical)
    #   Ensembl_proteinid  -> keep ENSP              (same)
    #   Uniprot_acc        -> keep SWISSPROT         (dbNSFP multi-isoform vs VEP versioned)
    #   genename           -> keep Hugo_Symbol       (dbNSFP duplicates per transcript)
    #   Gene.refGene       -> keep Hugo_Symbol       (87.6% match; boundary cases differ)
    #   CCDS_id            -> keep CCDS              (dbNSFP bare id vs VEP versioned)
    #   STRAND_VEP         -> keep STRAND            (completely empty column)
    #   cds_strand         -> keep STRAND            (same info, different encoding +/- vs 1/-1)
    #   am_class           -> keep AlphaMissense_pred (VEP single vs dbNSFP multi-transcript)
    #   am_pathogenicity   -> keep AlphaMissense_score (same)
    #   Func.ensGene       -> keep Func.refGene      (91.5% match, keep refGene)
    #   Uniprot_id         -> keep Uniprot_entry     (single vs multi-transcript mnemonic)
    T2="CLIN_SIG,Chr,#CHROM,#chr,HGVSc_VEP,Ensembl_transcriptid,Ensembl_proteinid,Uniprot_acc,genename,Gene.refGene,CCDS_id,STRAND_VEP,cds_strand,am_class,am_pathogenicity,Func.ensGene,Uniprot_id"
    #
    # DEAD — zero coverage in this file (MAF-standard fields never populated by pipeline)
    DEAD="gnomad_exomes_af,gnomad_genomes_af,Exon_Number,Entrez_Gene_Id,HGVSp_Short"

    DROP="\${ORIG},\${T1},\${T2},\${DEAD}"

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
