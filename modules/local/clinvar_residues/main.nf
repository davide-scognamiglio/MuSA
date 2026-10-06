/*
 * MuSA
 * Module: CLINVAR_RESIDUES
 * Purpose: ClinVar evidence at the variant's amino-acid residue (ACMG PS1 and PM5)
 *
 * Adds ClinVar_PS1 (the same amino-acid change is pathogenic in ClinVar through a different
 * nucleotide change) and ClinVar_PM5 (a different missense change at the residue is pathogenic),
 * from the index DOWNLOAD_CLINVAR_RESIDUES built; see bin/clinvar_residues.py.
 */

process CLINVAR_RESIDUES {
    tag "${meta.patient} | ClinVar PS1/PM5"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(maf)

    output:
        tuple val(meta), file("${maf.baseName}.residues.maf")

    script:
    """
    clinvar_residues.py annotate --maf ${maf} --index /data/clinvar_residues/clinvar_residues.tsv.gz \\
        --output ${maf.baseName}.residues.maf
    """
}
