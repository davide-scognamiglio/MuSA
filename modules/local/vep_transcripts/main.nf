/*
 * MuSA
 * Module: VEP_TRANSCRIPTS
 * Purpose: Every transcript's consequence for each variant, for the per-transcript sidecar
 *          (<patient>.transcripts.tsv.gz) and the report's transcript selector.
 *
 * A second, light VEP pass rather than --flag_pick on the main one: on NA12878 in extended mode,
 * --flag_pick ran every plugin on every transcript, 8 min 18 s and 966 MB instead of 2 min 43 s
 * and 61 MB. Here: the cache only, no plugins or custom files, transcript-level fields only, on a
 * sites-only copy. The main VEP run, its pick and the MAF are untouched.
 */

process VEP_TRANSCRIPTS {
    tag "${meta.patient} | every transcript"
    cpus params.n_core
    memory { 4.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2
    container params.vep_container

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("${meta.patient}.transcripts.vep.vcf")

    script:
        def fields = ['Allele', 'Consequence', 'IMPACT', 'SYMBOL', 'Gene', 'Feature_type', 'Feature',
                      'BIOTYPE', 'EXON', 'INTRON', 'HGVSc', 'HGVSp', 'cDNA_position', 'CDS_position',
                      'Protein_position', 'Amino_acids', 'Codons', 'STRAND', 'FLAGS', 'CANONICAL',
                      'MANE_SELECT', 'MANE_PLUS_CLINICAL', 'TSL', 'APPRIS', 'CCDS', 'ENSP',
                      'SWISSPROT', 'SIFT', 'PolyPhen'].join(',')
        """
        cut -f1-8 ${vcf} > sites.vcf

        vep \\
            -i sites.vcf \\
            --dir_cache "/data/vep_data/vep_cache" --safe \\
            --format vcf \\
            --fasta "/data/vep_data/reference_genome/${params.build}.fa" \\
            --vcf \\
            -o "${meta.patient}.transcripts.vep.vcf" \\
            --offline \\
            --assembly GRCh38 \\
            --symbol --biotype --numbers --hgvs --canonical --mane --appris --tsl --ccds \\
            --protein --uniprot --sift b --polyphen b \\
            --fields "${fields}" \\
            --fork ${params.n_core} \\
            --no_stats
        """
}
