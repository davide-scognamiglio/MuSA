/*
 * MuSA
 * Module: VEP_ANNOTATE_VCF
 * Purpose: Annotate variants using Ensembl VEP, optionally with plugins
 */


process VEP_ANNOTATE_VCF {
    tag "vep-annotation"
    cpus params.n_core
    errorStrategy 'retry'
    maxRetries 3
    memory { 8.GB * task.attempt }
    container "dsbioinfo/ensembl-vep:115.2"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.vep.vcf")

    script:
        """
        if [[ "${params.use_vep_plugins}" == "true" ]]; then
            echo "Running VEP with plugins..."
            vep \\
                -i $vcf \\
                --dir_plugins "/plugins" \\
                --dir_cache "/data/vep_data/vep_cache" --safe \\
                --format vcf \\
                --fasta "/data/vep_data/reference_genome/${params.build}.fa" \\
                --vcf \\
                -o "${meta.patient}.vep.vcf" \\
                --offline \\
                --assembly GRCh38 \\
                --mane --pick --everything --fork ${params.n_core} \\
                --verbose \\
                --plugin AlphaMissense,file="/data/vep_data/AlphaMissense/AlphaMissense_${params.build}.tsv.gz" \\
                --plugin AncestralAllele,"/data/vep_data/AncestralAllele/homo_sapiens_ancestor_GRCh38.fa.gz" \\
                --plugin CADD,snv="/data/vep_data/CADD/whole_genome_SNVs.tsv.gz" \\
                --plugin ClinPred,file="/data/vep_data/ClinPred/ClinPred_${params.build}_sorted_tabbed.tsv.gz" \\
                --plugin dbscSNV,"/data/vep_data/dbscSNV/dbscSNV1.1_GRCh38.txt.gz" \\
                --plugin Downstream \\
                --plugin Enformer,file="/data/vep_data/Enformer/enformer_grch38.vcf.gz" \\
                --plugin EVE,file="/data/vep_data/EVE/eve_merged.vcf.gz" \\
                --plugin HGVSIntronOffset \\
                --plugin MaveDB,file="/data/vep_data/MaveDB/MaveDB_variants.tsv.gz" \\
                --plugin MaxEntScan,"/data/vep_data/MaxEntScan/fordownload" \\
                --plugin mutfunc,motif=1,extended=1,db="/data/vep_data/mutfunc/mutfunc_data.db" \\
                --plugin NMD \\
                --plugin PhenotypeOrthologous,file="/data/vep_data/PhenotypeOrthologous/PhenotypesOrthologous_homo_sapiens_112_GRCh38.gff3.gz" \\
                --plugin ReferenceQuality,"/data/vep_data/ReferenceQuality/sorted_GRCh38_quality_mergedfile.gff3.gz" \\
                --plugin SingleLetterAA \\
                --plugin SpliceRegion \\
                --plugin SpliceVault,file="/data/vep_data/SpliceVault/SpliceVault_data_GRCh38.tsv.gz" \\
                --plugin TSSDistance \\
                --plugin UTRAnnotator,file="/data/vep_data/UTRannotator/uORF_5UTR_GRCh38_PUBLIC.txt" 
        else
            echo "Running VEP without plugins..."
            vep \\
                -i $vcf \\
                --dir_cache "/data/vep_data/vep_cache" --safe \\
                --format vcf \\
                --fasta "/data/vep_data/reference_genome/${params.build}.fa" \\
                --vcf \\
                -o "${meta.patient}.vep.vcf" \\
                --offline \\
                --assembly GRCh38 \\
                --mane --pick --everything --fork ${params.n_core} \\
                --verbose
        fi
        """
}