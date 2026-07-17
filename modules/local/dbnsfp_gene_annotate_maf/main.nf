/*
 * MuSA
 * Module: DBNSFP_GENE_ANNOTATE_MAF
 * Purpose: Extend dbNSFP's gene-level annotation to EVERY variant of a gene (join by Hugo_Symbol).
 *          The per-variant dbNSFP step matches on the amino-acid change, so it only fills the gene
 *          columns on missense/coding rows; every other variant of the same gene (intronic, UTR,
 *          splice, synonymous) is left empty even though the data is purely gene-level. This joins
 *          the dbNSFP *gene* file (one row per gene) and fills those columns for all rows.
 *          Fills existing columns only — the MAF keeps its exact width.
 *
 *          Runs AFTER clean_columns (final column names) and BEFORE clingen_annotate_maf, whose
 *          ClinGen dosage values are authoritative and must win over the gene file's older copies.
 */

process DBNSFP_GENE_ANNOTATE_MAF {
    tag "dbnsfp-gene-annotate"
    cpus params.n_core
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container 'dsbioinfo/musa-helper:rebuild'

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${meta.patient}.dbnsfp_gene.maf")

    script:
        """
        gene_file=\$(find /data/dbNSFP/dbNSFP -maxdepth 1 -name "*_gene.gz" | head -1)
        if [ -z "\$gene_file" ]; then
            echo "ERROR: no dbNSFP *_gene.gz under /data/dbNSFP/dbNSFP" >&2
            exit 1
        fi

        dbnsfp_gene_annotate_maf.py \\
            --input ${maf} \\
            --output ${meta.patient}.dbnsfp_gene.maf \\
            --gene-file "\$gene_file" \\
            --gene-col "Hugo_Symbol"
        """
}
