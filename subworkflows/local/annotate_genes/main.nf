include {DBNSFP_GENE_ANNOTATE_MAF} from '../../../modules/local/dbnsfp_gene_annotate_maf'
include {CLINGEN_ANNOTATE_MAF} from '../../../modules/local/clingen_annotate_maf'

/*
 * Stage 2 of ANNOTATE: what is known about each variant's gene.
 *
 *   DBNSFP_GENE_ANNOTATE_MAF  dbNSFP gene file: OMIM, Orphanet, GenCC, HPO, UniProt function,
 *                             GO, KEGG/BioCarta/ConsensusPathDB pathways, Human Protein Atlas
 *                             expression, gnomAD/ExAC constraint, RVIS, GDI, LoFtool,
 *                             haploinsufficiency and essentiality, MGI and ZFIN phenotypes
 *   CLINGEN_ANNOTATE_MAF      ClinGen gene–disease validity, dosage sensitivity, actionability
 *
 * dbNSFP first, then ClinGen: ClinGen's dosage values are authoritative and overwrite the gene
 * file's older ClinGen_Haploinsufficiency_* copies.
 */
workflow ANNOTATE_GENES {
    take: maf

    main:
        annotated = CLINGEN_ANNOTATE_MAF(DBNSFP_GENE_ANNOTATE_MAF(maf))

    emit:
        annotated
}
