include {DBNSFP_GENE_ANNOTATE_MAF} from '../../../modules/local/dbnsfp_gene_annotate_maf'
include {CLINGEN_ANNOTATE_MAF} from '../../../modules/local/clingen_annotate_maf'
include {HPO_MATCH} from '../../../modules/local/hpo_match'

/*
 * Stage 2 of ANNOTATE: what is known about each variant's gene.
 *
 *   DBNSFP_GENE_ANNOTATE_MAF  dbNSFP gene file: OMIM, Orphanet, GenCC, HPO, UniProt function,
 *                             GO, KEGG/BioCarta/ConsensusPathDB pathways, Human Protein Atlas
 *                             expression, gnomAD/ExAC constraint, RVIS, GDI, LoFtool,
 *                             haploinsufficiency and essentiality, MGI and ZFIN phenotypes
 *                             (extended mode: the gene file ships with dbNSFP)
 *   CLINGEN_ANNOTATE_MAF      ClinGen gene–disease validity, dosage sensitivity, actionability
 *   HPO_MATCH                 the patient's HPO terms against the gene's, with the native HPO
 *                             release: exact / narrower / broader match, similarity score,
 *                             best-matching disease, and the gene panel FILTER_VARIANTS uses
 *
 * dbNSFP first, then ClinGen: ClinGen's dosage values are authoritative and overwrite the gene
 * file's older ClinGen_Haploinsufficiency_* copies.
 */
workflow ANNOTATE_GENES {
    take: maf

    main:
        gene_file = params.extended ? DBNSFP_GENE_ANNOTATE_MAF(maf) : maf
        annotated = HPO_MATCH(CLINGEN_ANNOTATE_MAF(gene_file))

    emit:
        annotated
}
