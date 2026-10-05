# MuSA: Annotation sources

<!-- Generated from assets/annotation_sources.yaml by bin/musa_sources.py render. Edit the catalogue, not this file. -->

MuSA annotates every variant from **95 sources**: 67 at variant level, 25 at gene level, plus classification and filtering. Each row says what the source adds, which step brings it in, when it is active, and the MAF columns it fills (regular expressions).

When a run starts, MuSA prints the same list with the versions installed in `--data_dir`, and the report's **Sources** tab records what that run actually used.

Modes: **basic** is always on; **extended** needs `setup --download_vep_plugins true` and `annotate --use_vep_plugins true`; **online** needs `--offline false` (GeneBe credentials for ACMG).

## Variant level

### Consequence and transcript

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Ensembl / GENCODE gene models | Consequence, impact, transcript (MANE Select first), exon/intron, HGVS, HGNC symbol | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `Consequence`, `IMPACT`, `Hugo_Symbol`, `Gene`, `Feature_type`, `Feature`, `BIOTYPE`, `EXON`, `INTRON`, `HGVSc`, `cDNA_position`, `CDS_position`, `Protein_position`, `Amino_acids`, `Codons`, `DISTANCE`, `STRAND`, `FLAGS`, `VARIANT_CLASS`, `SYMBOL_SOURCE`, `HGNC_ID`, `CANONICAL`, `CCDS`, `ENSP`, `SOURCE`, `HGVS_OFFSET` |
| MANE (NCBI / EMBL-EBI) | MANE Select and MANE Plus Clinical transcript flags | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `MANE`, `MANE_SELECT`, `MANE_PLUS_CLINICAL` |
| UniProt (protein identifiers) | Swiss-Prot, TrEMBL and UniParc accessions of the affected protein | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `SWISSPROT`, `TREMBL`, `UNIPARC`, `UNIPROT_ISOFORM` |
| Protein domains (Pfam, PROSITE, SMART, …) | Protein domains and miRNA structures overlapped by the variant | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `DOMAINS`, `miRNA` |
| InterPro | InterPro domain of the affected residue | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `Interpro_domain` |
| dbNSFP transcript and coordinate fields ⁽ᶜ⁾ | Per-transcript IDs, HGVS (VEP and snpEff), codon details, GRCh37/hg18/T2T coordinates | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `aaref`, `aaalt`, `aapos`, `hg19_chr`, `hg19_pos\(1-based\)`, `hg18_chr`, `hg18_pos\(1-based\)`, `hs1_chr`, `hs1_pos\(1-based\)`, `Ensembl_transcriptid`, `Uniprot_entry`, `HGVSc_snpEff`, `HGVSp_VEP`, `GENCODE_basic`, `MANE_dbNSFP`, `refcodon`, `codonpos`, `codon_degeneracy` |
| VEP computed fields ⁽ᶜ⁾ | Downstream protein effect, NMD escape, splice region, TSS distance, intronic HGVS offsets (plugins Downstream, NMD, SpliceRegion, TSSDistance, HGVSIntronOffset, SingleLetterAA) | Ensembl VEP plugins (`VEP_ANNOTATE_VCF`) | extended | `DownstreamProtein`, `ProteinLengthChange`, `NMD`, `SpliceRegion`, `TSSDistance`, `HGVS_Intron.*` |

### Known variants and literature

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| dbSNP | rsIDs and other known-variant identifiers (COSMIC, HGMD public) at the same position | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `Existing_variation`, `rs_dbSNP` |
| Ensembl variation phenotypes and literature | Phenotype associations of the variant and gene, somatic status, PubMed IDs | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `GENE_PHENO`, `PHENO`, `SOMATIC`, `PUBMED` |
| GWAS Catalog | Published genome-wide associations of the variant (study, trait, p-value, effect) and of the gene *Gene-level traits from dbNSFP in both modes; variant-level GWAS_* columns from the VEP GWAS plugin in extended mode.* | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `GWAS_.*`, `Trait_association\(GWAS\)` |

### Clinical assertions

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| ClinVar | Clinical significance, review status, condition, conflicting submissions, cross-references | ClinVar (`VEP_ANNOTATE_VCF (--custom)`) | basic | `CLNSIG`, `CLNREVSTAT`, `CLNDN`, `CLNSIGCONF`, `CLNDISDB`, `CLNHGVS`, `GENEINFO`, `ALLELEID`, `ClinVar_RS`, `MC`, `encoded_CLNSIG`, `encoded_CLNREVSTAT`, `clinvar_id`, `clinvar_hgvs`, `clinvar_var_source`, `clinvar_MedGen_id`, `clinvar_OMIM_id`, `clinvar_Orphanet_id` |
| ClinGen expert-panel classifications | Variant classifications by ClinGen Variant Curation Expert Panels, with ACMG evidence codes | ClinGen Evidence Repository (`VEP_ANNOTATE_VCF (--custom)`) | basic | `ClinGenVCEP`, `ClinGen_Variant_.*` |

### Population frequency

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| gnomAD v4.1 | Exome, genome and joint allele frequencies by ancestry group; the maximum population frequency | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `gnomADe_.*`, `gnomADg_.*`, `gnomAD4\.1_joint.*`, `MAX_AF`, `MAX_AF_POPS` |
| gnomAD v2.1.1 | Exome frequencies in the controls, non-cancer and non-neuro subsets | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `gnomAD2\.1\.1_exomes_.*` |
| 1000 Genomes phase 3 | Allele frequencies in five continental groups | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `AF`, `AFR_AF`, `AMR_AF`, `EAS_AF`, `EUR_AF`, `SAS_AF`, `1000Gp3_.*` |
| TOPMed (freeze 8) | Allele frequencies from the NHLBI TOPMed programme | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `TOPMed_frz8_.*` |
| ALFA (NCBI) | Allele frequencies in 12 populations from dbGaP studies | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `ALFA_.*` |
| All of Us | Allele frequencies by ancestry group from the All of Us Research Program | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `AllofUs_.*` |
| Regeneron Genetics Center Million Exomes | Allele frequencies in about 30 populations (academic use only) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `RegeneronME_.*` |
| dbNSFP population maximum ⁽ᶜ⁾ | Highest frequency across the population databases dbNSFP carries | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `dbNSFP_POPMAX_.*` |
| Archaic hominin genomes | Genotypes of the Altai, Vindija and Chagyrskaya Neanderthals and the Denisovan | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `AltaiNeandertal`, `Denisova`, `VindijiaNeandertal`, `ChagyrskayaNeandertal` |

### Pathogenicity predictors

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| SIFT | Sequence-conservation missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `SIFT`, `SIFT_.*` |
| SIFT4G | Fast SIFT on a newer protein database | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `SIFT4G_.*` |
| PolyPhen-2 | Structure and conservation missense predictor (HumDiv and HumVar models) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `PolyPhen`, `Polyphen2_.*` |
| MutationTaster | Disease-causing potential of sequence changes | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MutationTaster_.*` |
| MutationAssessor | Functional impact from evolutionary conservation | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MutationAssessor_.*` |
| PROVEAN | Alignment-based impact of amino acid changes | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `PROVEAN_.*` |
| VEST4 | Random-forest missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `VEST4_.*` |
| MetaSVM | SVM ensemble of predictors | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MetaSVM_.*`, `Reliability_index` |
| MetaLR | Logistic-regression ensemble of predictors | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MetaLR_.*` |
| MetaRNN | Recurrent-neural-network ensemble | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MetaRNN_.*` |
| M-CAP | Clinical-grade missense classifier | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `M-CAP_.*` |
| REVEL | Ensemble missense score | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `REVEL_.*` |
| MutPred2 | Pathogenicity and likely molecular mechanisms | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MutPred2_.*` |
| MVP | Deep-learning missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MVP_.*` |
| gMVP | Graph-attention missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `gMVP_.*` |
| MisFit | Selection-based missense fitness (dominant and selection scores) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MisFit_.*` |
| MPC | Missense badness with regional constraint | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MPC_.*` |
| PrimateAI | Deep learning on primate variation | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `PrimateAI_.*` |
| DEOGEN2 | Variant and gene-level features combined | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `DEOGEN2_.*` |
| BayesDel | Bayesian deleteriousness score (with and without AF) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `BayesDel_.*` |
| ClinPred | Classifier trained on ClinVar | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `ClinPred_.*` |
| LIST-S2 | Taxonomy-aware conservation predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `LIST-S2_.*` |
| VARITY | Rare-variant-focused missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `VARITY_.*` |
| ESM1b | Protein language model | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `ESM1b_.*` |
| AlphaMissense | Protein structure-aware deep learning (Google DeepMind) *The VEP AlphaMissense plugin also runs in extended mode; its duplicate columns are dropped in favour of dbNSFP's.* | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `AlphaMissense_.*` |
| PHACTboost | Phylogeny-aware gradient boosting | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `PHACTboost_.*` |
| MutFormer | Transformer protein language model | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MutFormer_.*` |
| MutScore | Positional clustering of pathogenic variants | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `MutScore_.*` |
| popEVE | Evolutionary model calibrated across the proteome | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `popEVE_.*` |
| ALoFT | Loss-of-function variants classified as tolerated, recessive or dominant | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `Aloft_.*` |
| CADD | Genome-wide deleteriousness (PHRED-scaled) *PHRED and raw scores from the VEP plugin in extended mode; the rank score from dbNSFP in both modes.* | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `CADD_PHRED`, `CADD_RAW`, `CADD_raw_rankscore` |
| DANN | Deep-network deleteriousness | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `DANN_.*` |
| fathmm-XF | Coding-variant pathogenicity | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `fathmm-XF_.*` |
| Eigen | Unsupervised functional score (Eigen and Eigen-PC) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `Eigen-.*` |
| EVE | Evolutionary model of variant effect | VEP plugin EVE (`VEP_ANNOTATE_VCF`) | extended | `EVE_.*` |

### Splicing

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| SpliceVault | Mis-splicing events seen in RNA-seq, with the SpliceAI delta | VEP plugin SpliceVault (`VEP_ANNOTATE_VCF`) | extended | `SpliceVault_.*` |
| MaxEntScan | Splice-site strength before and after the variant | VEP plugin MaxEntScan (`VEP_ANNOTATE_VCF`) | extended | `MaxEntScan_.*` |
| dbscSNV | Ensemble splice-altering predictions (AdaBoost and random forest) | VEP plugin dbscSNV (`VEP_ANNOTATE_VCF`) | extended | `ada_score`, `rf_score` |

### Regulatory and functional

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Ensembl Regulatory Build | Transcription-factor motifs and binding changes | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `MOTIF_NAME`, `MOTIF_POS`, `HIGH_INF_POS`, `MOTIF_SCORE_CHANGE`, `TRANSCRIPTION_FACTORS` |
| Enformer | Predicted effect on gene expression (deep learning) | VEP plugin Enformer (`VEP_ANNOTATE_VCF`) | extended | `Enformer_.*` |
| UTRannotator | Effect of 5′UTR variants on upstream open reading frames | VEP plugin UTRAnnotator (`VEP_ANNOTATE_VCF`) | extended | `5UTR_.*`, `Existing_InFrame_oORFs`, `Existing_OutOfFrame_oORFs`, `Existing_uORFs` |
| MaveDB | Scores from multiplexed assays of variant effect | VEP plugin MaveDB (`VEP_ANNOTATE_VCF`) | extended | `MaveDB_.*` |
| mutfunc | Predicted effect on linear motifs | VEP plugin mutfunc (`VEP_ANNOTATE_VCF`) | extended | `mutfunc_.*` |
| Ensembl ancestral alleles | Inferred ancestral allele from primate alignments *AA from the VEP plugin (extended); Ancestral_allele from dbNSFP (both modes).* | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `AA`, `Ancestral_allele` |
| GRC reference issues | Known problems of the reference genome at the variant site | VEP plugin ReferenceQuality (`VEP_ANNOTATE_VCF`) | extended | `ReferenceQuality` |

### Conservation

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| GERP++ / GERP (92 mammals) | Constrained-element rejected substitutions | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `GERP\+\+_.*`, `GERP_92_mammals.*` |
| phyloP | Base-wise conservation in vertebrates, mammals and primates | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `phyloP.*` |
| phastCons | Conserved-element probability in vertebrates, mammals and primates | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `phastCons.*` |
| B statistic | Background selection | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | basic | `bStatistic.*` |

## Gene level

### Gene–disease

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| ClinGen gene–disease validity | Strength of evidence that the gene causes the disease, and mode of inheritance | ClinGen gene curations (`CLINGEN_ANNOTATE_MAF`) | basic | `ClinGen_GeneDisease_.*` |
| ClinGen dosage sensitivity | Haploinsufficiency and triplosensitivity scores | ClinGen gene curations (`CLINGEN_ANNOTATE_MAF`) | basic | `ClinGen_Haploinsufficiency_.*`, `ClinGen_Triplosensitivity_.*` |
| ClinGen actionability | Clinical actionability for adult and paediatric contexts | ClinGen gene curations (`CLINGEN_ANNOTATE_MAF`) | basic | `ClinGen_Actionability_.*` |
| OMIM | Mendelian disorders linked to the gene | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `OMIM_id`, `MIM_phenotype_id`, `MIM_disease` |
| Orphanet | Rare diseases linked to the gene and the type of association | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Orphanet_.*` |
| GenCC | Harmonised gene–disease validity from multiple curators | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `GenCC_.*` |
| Human Phenotype Ontology | Phenotype terms annotated to the gene | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `HPO_id`, `HPO_name` |

### Function and pathways

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| UniProt (function) | Protein function, disease involvement, tissue specificity and pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Function_description`, `Disease_description`, `Tissue_specificity\(Uniprot\)`, `Pathway\(Uniprot\)` |
| Gene Ontology | Biological process, cellular component and molecular function | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `GO_.*` |
| KEGG | Pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Pathway\(KEGG\)_.*` |
| BioCarta | Pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Pathway\(BioCarta\)_.*` |
| ConsensusPathDB | Integrated pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Pathway\(ConsensusPathDB\)` |
| Gene identifiers (HGNC, NCBI Gene, RefSeq, UCSC) | Full name, previous and alternative symbols, cross-references | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Gene_old_names`, `Gene_other_names`, `Entrez_gene_id`, `Refseq_id`, `ucsc_id`, `Gene_full_name` |

### Expression

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Human Protein Atlas | Consensus RNA expression in 50 tissues | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `HPA_consensus_.*` |

### Constraint and dosage

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| gnomAD gene constraint | pLI, LOEUF, missense and LoF observed/expected | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `gnomAD_pLI`, `gnomAD_pRec`, `gnomAD_pNull`, `gnomAD_lof.oe`, `gnomAD_mis.oe`, `gnomAD_LOEUF`, `gnomAD_MOEUF` |
| ExAC gene constraint | pLI (all, non-TCGA, non-psych), CNV scores, LoF FDR *pLI_gene_value comes from the VEP pLI plugin in extended mode.* | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `ExAC_.*`, `LoF-FDR_ExAC`, `pLI_gene_value` |
| RVIS | Residual variation intolerance (EVS and ExAC) | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `RVIS_.*` |
| Gene Damage Index | Accumulated mutational damage and disease-gene predictions | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `GDI`, `GDI-Phred`, `Gene damage prediction .*` |
| LoFtool | Gene intolerance to loss of function | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `LoFtool_score` |
| Haploinsufficiency predictions | P(HI) (Huang et al.), HIPred and GHIS | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `P\(HI\)`, `HIPred_score`, `HIPred`, `GHIS` |
| Recessive disease genes | Probability of being a recessive disease gene, known recessive status | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `P\(rec\)`, `Known_rec_info` |
| Essential genes | Essentiality from CRISPR and gene-trap screens, indispensability | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `Essential_gene.*`, `Gene_indispensability_.*` |

### Model organisms

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| MGI (mouse) | Mouse orthologue and its phenotypes | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `MGI_.*` |
| ZFIN (zebrafish) | Zebrafish orthologue and its phenotypes | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | basic | `ZFIN_.*` |
| Ensembl orthologue phenotypes | Phenotypes of the mouse and rat orthologues | VEP plugin PhenotypeOrthologous (`VEP_ANNOTATE_VCF`) | extended | `PhenotypeOrthologous_.*` |

## Scores and classification

### Classification

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| RENOVO 1.5 | Machine-learning pathogenicity probability and six-class call for every variant | renovo-rebuild (`RENOVO_SCORE`) | basic | `RENOVO_Class`, `PL_score` |
| GeneBe ACMG/AMP | Automated ACMG/AMP criteria and points-based score | GeneBe API (`GENEBE_ANNOTATE_VCF`) | online | `acmg_.*` |
| RENOVO-adjusted ACMG score ⁽ᶜ⁾ | GeneBe's ACMG score moved toward pathogenic or benign by RENOVO for missense variants | MuSA (`MERGE_ANNOTATIONS, ADD_GENOME_CHANGE, ADD_REF_CONTEXT, ENCODE_CLINVAR`) | online | `renovo_adj_acmg_score` |

## Filtering

### Filtering

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| HPO gene panel (JAX) | Genes annotated to the patient's HPO terms, used to filter the variants | JAX HPO API (`FILTER_VARIANTS`) | online | none (filters rows) |

## Call information and MAF format

Not annotation sources, but every column of the MAF is accounted for:

| Fields | What they hold | Columns |
|---|---|---|
| Input VCF | Call quality, filter status, genotype and the original INFO and FORMAT fields | `QUAL`, `FILTER`, `bioinfo_params`, `FORMAT_FIELDS`, `FORMAT_VALUES`, `INFO`, `FORMAT`, `{sample}` |
| MAF format (vcf2maf) | Standard MAF columns, genomic coordinates, picked-transcript fields | `Center`, `NCBI_Build`, `Chromosome`, `Start_Position`, `End_Position`, `Strand`, `Variant_Classification`, `Variant_Type`, `Reference_Allele`, `Tumor_Seq_Allele1`, `Tumor_Seq_Allele2`, `dbSNP_RS`, `dbSNP_Val_Status`, `Tumor_Sample_Barcode`, `Matched_Norm_Sample_Barcode`, `Match_Norm_Seq_Allele1`, `Match_Norm_Seq_Allele2`, `Tumor_Validation_Allele1`, `Tumor_Validation_Allele2`, `Match_Norm_Validation_Allele1`, `Match_Norm_Validation_Allele2`, `Verification_Status`, `Validation_Status`, `Mutation_Status`, `Sequencing_Phase`, `Sequence_Source`, `Validation_Method`, `Score`, `BAM_File`, `Sequencer`, `Tumor_Sample_UUID`, `Matched_Norm_Sample_UUID`, `Transcript_ID`, `t_depth`, `t_ref_count`, `t_alt_count`, `n_depth`, `n_ref_count`, `n_alt_count`, `all_effects`, `ALLELE_NUM`, `RefSeq`, `ASN_AF`, `AA_AF`, `EA_AF`, `PICK`, `MINIMISED`, `flanking_bps`, `vcf_id`, `vcf_ref`, `vcf_alt` |
| MuSA sequence context | Genome change notation and reference sequence context | `genome_change`, `ref_context` |

⁽ᶜ⁾ derived by a tool rather than taken from an external resource; not counted among the sources above.
