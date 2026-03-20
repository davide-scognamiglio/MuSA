/*
 * MuSA
 * Module: DOWNLOAD_REFERENCEQUALITY
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_REFERENCEQUALITY {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"
    
    output:
    path "ReferenceQuality"

    script:
    """
    mkdir -p ReferenceQuality
    cd ReferenceQuality
    wget https://ftp.ncbi.nlm.nih.gov/pub/grc/human/GRC/GRCh38/MISC/annotated_clone_assembly_problems_GCF_000001405.38.gff3
    wget https://ftp.ncbi.nlm.nih.gov/pub/grc/human/GRC/Issue_Mapping/GRCh38.p12_issues.gff3
    cat annotated_clone_assembly_problems_GCF_000001405.38.gff3 GRCh38.p12_issues.gff3 > GRCh38_quality_mergedfile.gff3
    sort -k1,1 -k4,4n -k5,5n GRCh38_quality_mergedfile.gff3 > sorted_GRCh38_quality_mergedfile.gff3
    bgzip sorted_GRCh38_quality_mergedfile.gff3
    tabix -p gff sorted_GRCh38_quality_mergedfile.gff3.gz
    cd ..
    """
}