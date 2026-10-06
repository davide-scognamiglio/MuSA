# MuSA: Annotation sources

<!-- Generated from assets/annotation_sources.yaml by bin/musa_sources.py render. Edit the catalogue, not this file. -->

MuSA annotates every variant from **103 sources**: 72 at variant level, 29 at gene level, plus classification and filtering. Each row says what the source adds, which step brings it in, when it is active, and the MAF columns it fills (regular expressions).

When a run starts, MuSA prints the same list with the versions installed in `--data_dir`, and the report's **Annotation sources** view records what that run actually used.

Modes: **basic** is always on; **extended** (dbNSFP, RENOVO 1.5 and the VEP plugins) needs `setup --extended true` and `annotate --extended true`; **online** needs `--offline false` (GeneBe credentials for ACMG); **extended+online** needs both.

## Variant level

### Consequence and transcript

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Ensembl / GENCODE gene models | Consequence, impact, transcript (MANE Select first), exon/intron, HGVS, HGNC symbol | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `Consequence`, `IMPACT`, `Hugo_Symbol`, `Gene`, `Feature_type`, `Feature`, `BIOTYPE`, `EXON`, `INTRON`, `HGVSc`, `cDNA_position`, `CDS_position`, `Protein_position`, `Amino_acids`, `Codons`, `DISTANCE`, `STRAND`, `FLAGS`, `VARIANT_CLASS`, `SYMBOL_SOURCE`, `HGNC_ID`, `CANONICAL`, `CCDS`, `ENSP`, `SOURCE`, `HGVS_OFFSET` |
| MANE (NCBI / EMBL-EBI) | MANE Select and MANE Plus Clinical transcript flags | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `MANE`, `MANE_SELECT`, `MANE_PLUS_CLINICAL` |
| UniProt (protein identifiers) | Swiss-Prot, TrEMBL and UniParc accessions of the affected protein | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `SWISSPROT`, `TREMBL`, `UNIPARC`, `UNIPROT_ISOFORM` |
| Protein domains (Pfam, PROSITE, SMART, …) | Protein domains and miRNA structures overlapped by the variant | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `DOMAINS`, `miRNA` |
| InterPro | InterPro domain of the affected residue | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `Interpro_domain` |
| dbNSFP transcript and coordinate fields ⁽ᶜ⁾ | Per-transcript IDs, HGVS (VEP and snpEff), codon details, GRCh37/hg18/T2T coordinates | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `aaref`, `aaalt`, `aapos`, `hg19_chr`, `hg19_pos\(1-based\)`, `hg18_chr`, `hg18_pos\(1-based\)`, `hs1_chr`, `hs1_pos\(1-based\)`, `Ensembl_transcriptid`, `Uniprot_entry`, `HGVSc_snpEff`, `HGVSp_VEP`, `GENCODE_basic`, `MANE_dbNSFP`, `refcodon`, `codonpos`, `codon_degeneracy` |
| GENCODE Ribo-seq ORFs | Consequence on translated ORFs outside the annotated coding sequence (uORFs, lncRNA ORFs) | VEP plugin RiboseqORFs (`VEP_ANNOTATE_VCF`) | extended | `RiboseqORFs_.*` |
| Locus Reference Genomic (LRG) | LRG record of the transcript, the stable reference used in clinical reports | VEP plugin FlagLRG (`VEP_ANNOTATE_VCF`) | extended | `FlagLRG` |
| VEP computed fields ⁽ᶜ⁾ | Downstream protein effect, NMD escape, splice region, TSS distance, intronic HGVS offsets, nearest exon junction, nearest gene of intergenic variants, BLOSUM62 substitution score (plugins Downstream, NMD, SpliceRegion, TSSDistance, HGVSIntronOffset, SingleLetterAA, NearestExonJB, NearestGene, Blosum62) | Ensembl VEP plugins (`VEP_ANNOTATE_VCF`) | extended | `DownstreamProtein`, `ProteinLengthChange`, `NMD`, `SpliceRegion`, `TSSDistance`, `HGVS_Intron.*`, `NearestExonJB`, `NearestGene`, `BLOSUM62` |

### Known variants and literature

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| dbSNP | rsIDs and other known-variant identifiers (COSMIC, HGMD public) at the same position | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `Existing_variation`, `rs_dbSNP` |
| Ensembl variation phenotypes and literature | Phenotype associations of the variant and gene, somatic status, PubMed IDs | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `GENE_PHENO`, `PHENO`, `SOMATIC`, `PUBMED` |
| GWAS Catalog | Published genome-wide associations of the variant (study, trait, p-value, effect) and of the gene *Gene-level traits from dbNSFP's gene file, variant-level GWAS_* columns from the VEP GWAS plugin.* | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `GWAS_.*`, `Trait_association\(GWAS\)` |

### Clinical assertions

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| ClinVar | Clinical significance, review status, condition, conflicting submissions, cross-references | ClinVar (`VEP_ANNOTATE_VCF (--custom)`) | basic | `CLNSIG`, `CLNREVSTAT`, `CLNDN`, `CLNSIGCONF`, `CLNDISDB`, `CLNHGVS`, `GENEINFO`, `ALLELEID`, `ClinVar_RS`, `MC`, `encoded_CLNSIG`, `encoded_CLNREVSTAT`, `clinvar_id`, `clinvar_hgvs`, `clinvar_var_source`, `clinvar_MedGen_id`, `clinvar_OMIM_id`, `clinvar_Orphanet_id` |
| ClinGen expert-panel classifications | Variant classifications by ClinGen Variant Curation Expert Panels, with ACMG evidence codes | ClinGen Evidence Repository (`VEP_ANNOTATE_VCF (--custom)`) | basic | `ClinGenVCEP`, `ClinGen_Variant_.*` |

### Population frequency

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| gnomAD v4.1 | Exome, genome and joint allele frequencies by ancestry group; the maximum population frequency | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `gnomADe_.*`, `gnomADg_.*`, `gnomAD4\.1_joint.*`, `MAX_AF`, `MAX_AF_POPS` |
| gnomAD v2.1.1 | Exome frequencies in the controls, non-cancer and non-neuro subsets | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `gnomAD2\.1\.1_exomes_.*` |
| 1000 Genomes phase 3 | Allele frequencies in five continental groups | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `AF`, `AFR_AF`, `AMR_AF`, `EAS_AF`, `EUR_AF`, `SAS_AF`, `1000Gp3_.*` |
| TOPMed (freeze 8) | Allele frequencies from the NHLBI TOPMed programme | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `TOPMed_frz8_.*` |
| ALFA (NCBI) | Allele frequencies in 12 populations from dbGaP studies | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `ALFA_.*` |
| All of Us | Allele frequencies by ancestry group from the All of Us Research Program | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `AllofUs_.*` |
| Regeneron Genetics Center Million Exomes | Allele frequencies in about 30 populations (academic use only) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `RegeneronME_.*` |
| dbNSFP population maximum ⁽ᶜ⁾ | Highest frequency across the population databases dbNSFP carries | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `dbNSFP_POPMAX_.*` |
| Archaic hominin genomes | Genotypes of the Altai, Vindija and Chagyrskaya Neanderthals and the Denisovan | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `AltaiNeandertal`, `Denisova`, `VindijiaNeandertal`, `ChagyrskayaNeandertal` |

### Pathogenicity predictors

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| SIFT | Sequence-conservation missense predictor, for the transcript VEP picked | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `SIFT` |
| SIFT (dbNSFP) ⁽ʳ⁾ | SIFT scores and predictions across transcripts | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `SIFT_.*` |
| SIFT4G | Fast SIFT on a newer protein database | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `SIFT4G_.*` |
| PolyPhen-2 | Structure and conservation missense predictor, for the transcript VEP picked | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `PolyPhen` |
| PolyPhen-2 (dbNSFP) ⁽ʳ⁾ | PolyPhen-2 HumDiv and HumVar scores and predictions across transcripts | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `Polyphen2_.*` |
| MutationTaster | Disease-causing potential of sequence changes | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MutationTaster_.*` |
| MutationAssessor | Functional impact from evolutionary conservation | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MutationAssessor_.*` |
| PROVEAN | Alignment-based impact of amino acid changes | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `PROVEAN_.*` |
| VEST4 | Random-forest missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `VEST4_.*` |
| MetaSVM | SVM ensemble of predictors | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MetaSVM_.*`, `Reliability_index` |
| MetaLR | Logistic-regression ensemble of predictors | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MetaLR_.*` |
| MetaRNN | Recurrent-neural-network ensemble | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MetaRNN_.*` |
| M-CAP | Clinical-grade missense classifier | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `M-CAP_.*` |
| REVEL | Ensemble missense score | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `REVEL_.*` |
| MutPred2 | Pathogenicity and likely molecular mechanisms | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MutPred2_.*` |
| MVP | Deep-learning missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MVP_.*` |
| gMVP | Graph-attention missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `gMVP_.*` |
| MisFit | Selection-based missense fitness (dominant and selection scores) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MisFit_.*` |
| MPC | Missense badness with regional constraint | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MPC_.*` |
| PrimateAI | Deep learning on primate variation | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `PrimateAI_.*` |
| DEOGEN2 | Variant and gene-level features combined | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `DEOGEN2_.*` |
| BayesDel | Bayesian deleteriousness score (with and without AF) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `BayesDel_.*` |
| ClinPred | Classifier trained on ClinVar | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `ClinPred_.*` |
| LIST-S2 | Taxonomy-aware conservation predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `LIST-S2_.*` |
| VARITY | Rare-variant-focused missense predictor | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `VARITY_.*` |
| ESM1b | Protein language model | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `ESM1b_.*` |
| AlphaMissense | Protein structure-aware deep learning (Google DeepMind) *From dbNSFP, read on the MANE transcript; rows dbNSFP leaves empty are filled from the VEP AlphaMissense plugin, and AlphaMissense_source says which copy each row holds.* | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `AlphaMissense_.*` |
| PHACTboost | Phylogeny-aware gradient boosting | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `PHACTboost_.*` |
| MutFormer | Transformer protein language model | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MutFormer_.*` |
| MutScore | Positional clustering of pathogenic variants | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `MutScore_.*` |
| popEVE | Evolutionary model calibrated across the proteome | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `popEVE_.*` |
| ALoFT | Loss-of-function variants classified as tolerated, recessive or dominant | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `Aloft_.*` |
| CADD | Genome-wide deleteriousness (PHRED-scaled) *PHRED and raw scores from the VEP plugin; the rank score from dbNSFP.* | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `CADD_PHRED`, `CADD_RAW`, `CADD_raw_rankscore` |
| DANN | Deep-network deleteriousness | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `DANN_.*` |
| fathmm-XF | Coding-variant pathogenicity | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `fathmm-XF_.*` |
| Eigen | Unsupervised functional score (Eigen and Eigen-PC) | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `Eigen-.*` |
| EVE | Evolutionary model of variant effect | VEP plugin EVE (`VEP_ANNOTATE_VCF`) | extended | `EVE_.*` |

### Splicing

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| SpliceAI | Predicted splice-site gain and loss (delta scores and positions), SNVs on MANE transcripts *Ensembl's masked scores; indels have none (Illumina distributes their scores only through BaseSpace).* | VEP plugin SpliceAI (`VEP_ANNOTATE_VCF`) | extended | `SpliceAI_pred.*` |
| SpliceVault | Mis-splicing events seen in RNA-seq, with the SpliceAI delta | VEP plugin SpliceVault (`VEP_ANNOTATE_VCF`) | extended | `SpliceVault_.*` |
| MaxEntScan | Splice-site strength before and after the variant | VEP plugin MaxEntScan (`VEP_ANNOTATE_VCF`) | extended | `MaxEntScan_.*` |
| dbscSNV | Ensemble splice-altering predictions (AdaBoost and random forest) | VEP plugin dbscSNV (`VEP_ANNOTATE_VCF`) | extended | `ada_score`, `rf_score` |

### Regulatory and functional

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| ProtVar | Missense structural context: predicted stability change, AlphaFold pockets, protein-protein interfaces | VEP plugin ProtVar (`VEP_ANNOTATE_VCF`) | extended | `ProtVar_.*` |
| IntAct | Molecular interactions experimentally affected by mutations at the variant | VEP plugin IntAct (`VEP_ANNOTATE_VCF`) | extended | `IntAct_.*` |
| Ensembl Regulatory Build | Transcription-factor motifs and binding changes | Ensembl VEP cache (`VEP_ANNOTATE_VCF`) | basic | `MOTIF_NAME`, `MOTIF_POS`, `HIGH_INF_POS`, `MOTIF_SCORE_CHANGE`, `TRANSCRIPTION_FACTORS` |
| Enformer | Predicted effect on gene expression (deep learning) | VEP plugin Enformer (`VEP_ANNOTATE_VCF`) | extended | `Enformer_.*` |
| UTRannotator | Effect of 5′UTR variants on upstream open reading frames | VEP plugin UTRAnnotator (`VEP_ANNOTATE_VCF`) | extended | `5UTR_.*`, `Existing_InFrame_oORFs`, `Existing_OutOfFrame_oORFs`, `Existing_uORFs` |
| MaveDB | Scores from multiplexed assays of variant effect | VEP plugin MaveDB (`VEP_ANNOTATE_VCF`) | extended | `MaveDB_.*` |
| mutfunc | Predicted effect on linear motifs | VEP plugin mutfunc (`VEP_ANNOTATE_VCF`) | extended | `mutfunc_.*` |
| Ensembl ancestral alleles | Inferred ancestral allele from primate alignments *AA from the VEP plugin; Ancestral_allele from dbNSFP.* | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `AA`, `Ancestral_allele` |
| GRC reference issues | Known problems of the reference genome at the variant site | VEP plugin ReferenceQuality (`VEP_ANNOTATE_VCF`) | extended | `ReferenceQuality` |

### Conservation

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| GERP++ / GERP (92 mammals) | Constrained-element rejected substitutions | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `GERP\+\+_.*`, `GERP_92_mammals.*` |
| phyloP | Base-wise conservation in vertebrates, mammals and primates | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `phyloP.*` |
| phastCons | Conserved-element probability in vertebrates, mammals and primates | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `phastCons.*` |
| B statistic | Background selection | dbNSFP (`DBNSFP_ANNOTATE_VCF_CHR`) | extended | `bStatistic.*` |

## Gene level

### Gene–disease

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Gene2Phenotype (G2P) | Flags variants whose zygosity and frequency fit the gene's allelic requirement in G2P | VEP plugin G2P (`VEP_ANNOTATE_VCF`) | extended | `G2P_.*` |
| ClinGen gene–disease validity | Strength of evidence that the gene causes the disease, and mode of inheritance | ClinGen gene curations (`CLINGEN_ANNOTATE_MAF`) | basic | `ClinGen_GeneDisease_.*` |
| ClinGen dosage sensitivity | Haploinsufficiency and triplosensitivity scores | ClinGen gene curations (`CLINGEN_ANNOTATE_MAF`) | basic | `ClinGen_Haploinsufficiency_.*`, `ClinGen_Triplosensitivity_.*` |
| ClinGen actionability | Clinical actionability for adult and paediatric contexts | ClinGen gene curations (`CLINGEN_ANNOTATE_MAF`) | basic | `ClinGen_Actionability_.*` |
| OMIM | Mendelian disorders linked to the gene | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `OMIM_id`, `MIM_phenotype_id`, `MIM_disease` |
| Orphanet | Rare diseases linked to the gene and the type of association | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Orphanet_.*` |
| GenCC | Harmonised gene–disease validity from multiple curators | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `GenCC_.*` |
| HPO gene terms (dbNSFP) | Phenotype terms annotated to the gene, as dbNSFP carries them | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `HPO_id`, `HPO_name` |

### Constraint and dosage

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| MechPredict | Predicted disease mechanism of the gene: dominant-negative, gain- or loss-of-function | VEP plugin MechPredict (`VEP_ANNOTATE_VCF`) | extended | `MechPredict_.*` |
| Dosage sensitivity (Collins 2022) | Probability that the gene is haploinsufficient (pHaplo) or triplosensitive (pTriplo), from rare CNVs | VEP plugin DosageSensitivity (`VEP_ANNOTATE_VCF`) | extended | `pHaplo`, `pTriplo` |
| gnomAD gene constraint | pLI, LOEUF, missense and LoF observed/expected | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `gnomAD_pLI`, `gnomAD_pRec`, `gnomAD_pNull`, `gnomAD_lof.oe`, `gnomAD_mis.oe`, `gnomAD_LOEUF`, `gnomAD_MOEUF` |
| ExAC gene constraint | pLI (all, non-TCGA, non-psych), CNV scores, LoF FDR *pLI_gene_value comes from the VEP pLI plugin.* | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `ExAC_.*`, `LoF-FDR_ExAC`, `pLI_gene_value` |
| RVIS | Residual variation intolerance (EVS and ExAC) | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `RVIS_.*` |
| Gene Damage Index | Accumulated mutational damage and disease-gene predictions | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `GDI`, `GDI-Phred`, `Gene damage prediction .*` |
| LoFtool | Gene intolerance to loss of function | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `LoFtool_score` |
| Haploinsufficiency predictions | P(HI) (Huang et al.), HIPred and GHIS | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `P\(HI\)`, `HIPred_score`, `HIPred`, `GHIS` |
| Recessive disease genes | Probability of being a recessive disease gene, known recessive status | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `P\(rec\)`, `Known_rec_info` |
| Essential genes | Essentiality from CRISPR and gene-trap screens, indispensability | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Essential_gene.*`, `Gene_indispensability_.*` |

### Function and pathways

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| UniProt (function) | Protein function, disease involvement, tissue specificity and pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Function_description`, `Disease_description`, `Tissue_specificity\(Uniprot\)`, `Pathway\(Uniprot\)` |
| Gene Ontology | Biological process, cellular component and molecular function | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `GO_.*` |
| KEGG | Pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Pathway\(KEGG\)_.*` |
| BioCarta | Pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Pathway\(BioCarta\)_.*` |
| ConsensusPathDB | Integrated pathways | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Pathway\(ConsensusPathDB\)` |
| Gene identifiers (HGNC, NCBI Gene, RefSeq, UCSC) | Full name, previous and alternative symbols, cross-references | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `Gene_old_names`, `Gene_other_names`, `Entrez_gene_id`, `Refseq_id`, `ucsc_id`, `Gene_full_name` |

### Expression

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Human Protein Atlas | Consensus RNA expression in 50 tissues | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `HPA_consensus_.*` |

### Model organisms

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| MGI (mouse) | Mouse orthologue and its phenotypes | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `MGI_.*` |
| ZFIN (zebrafish) | Zebrafish orthologue and its phenotypes | dbNSFP gene file (`DBNSFP_GENE_ANNOTATE_MAF`) | extended | `ZFIN_.*` |
| Ensembl orthologue phenotypes | Phenotypes of the mouse and rat orthologues | VEP plugin PhenotypeOrthologous (`VEP_ANNOTATE_VCF`) | extended | `PhenotypeOrthologous_.*` |

### Patient phenotype

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| Human Phenotype Ontology (ontology and annotations) | The patient's HPO terms against the gene's: exact, narrower or broader match, similarity score, best-matching OMIM/Orphanet disease, and the phenotype gene panel the filtered MAF uses *Native HPO release (hp.obo, genes_to_phenotype.txt, phenotype.hpoa); filled only when the samplesheet gives HPO terms.* | Human Phenotype Ontology (`HPO_MATCH`) | basic | `HPO_match`, `HPO_match_score`, `HPO_matched_terms`, `HPO_best_disease`, `HPO_panel` |

## Scores and classification

### Classification

| Source | What it adds | Brought in by | Mode | Columns |
|---|---|---|---|---|
| RENOVO 1.5 | Machine-learning pathogenicity probability and six-class call for every variant | renovo-rebuild (`RENOVO_SCORE`) | extended | `RENOVO_Class`, `PL_score` |
| GeneBe ACMG/AMP | Automated ACMG/AMP criteria and points-based score | GeneBe API (`GENEBE_ANNOTATE_VCF`) | online | `acmg_.*` |
| RENOVO-adjusted ACMG score ⁽ᶜ⁾ | GeneBe's ACMG score moved toward pathogenic or benign by RENOVO for missense variants | MuSA (`RENOVO_ADJUST_ACMG`) | extended+online | `renovo_adj_acmg_score` |
| ClinVar residue evidence (PS1, PM5) ⁽ᶜ⁾ | Pathogenic ClinVar variants at the same amino-acid residue: the same change from another nucleotide change (PS1), or another change (PM5) | ClinVar variant summary (`CLINVAR_RESIDUES`) | basic | `ClinVar_PS1`, `ClinVar_PM5` |

## Call information and MAF format

Not annotation sources, but every column of the MAF is accounted for:

| Fields | What they hold | Columns |
|---|---|---|
| Input VCF | Call quality, filter status, genotype and the original INFO and FORMAT fields | `QUAL`, `FILTER`, `bioinfo_params`, `FORMAT_FIELDS`, `FORMAT_VALUES`, `INFO`, `FORMAT`, `{sample}` |
| MAF format (vcf2maf) | Standard MAF columns, genomic coordinates, picked-transcript fields | `Center`, `NCBI_Build`, `Chromosome`, `Start_Position`, `End_Position`, `Strand`, `Variant_Classification`, `Variant_Type`, `Reference_Allele`, `Tumor_Seq_Allele1`, `Tumor_Seq_Allele2`, `dbSNP_RS`, `dbSNP_Val_Status`, `Tumor_Sample_Barcode`, `Matched_Norm_Sample_Barcode`, `Match_Norm_Seq_Allele1`, `Match_Norm_Seq_Allele2`, `Tumor_Validation_Allele1`, `Tumor_Validation_Allele2`, `Match_Norm_Validation_Allele1`, `Match_Norm_Validation_Allele2`, `Verification_Status`, `Validation_Status`, `Mutation_Status`, `Sequencing_Phase`, `Sequence_Source`, `Validation_Method`, `Score`, `BAM_File`, `Sequencer`, `Tumor_Sample_UUID`, `Matched_Norm_Sample_UUID`, `Transcript_ID`, `t_depth`, `t_ref_count`, `t_alt_count`, `n_depth`, `n_ref_count`, `n_alt_count`, `all_effects`, `ALLELE_NUM`, `RefSeq`, `ASN_AF`, `AA_AF`, `EA_AF`, `PICK`, `MINIMISED`, `flanking_bps`, `vcf_id`, `vcf_ref`, `vcf_alt` |
| MuSA sequence context | Genome change notation and reference sequence context | `genome_change`, `ref_context` |

⁽ᶜ⁾ derived by a tool rather than taken from an external resource; not counted among the sources above.

⁽ʳ⁾ a resource already listed, reached through a second provider; counted once.
