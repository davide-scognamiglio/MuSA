/*
 * MuSA
 * Module: DOWNLOAD_CLINPRED
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_CLINPRED {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true
    container "dsbioinfo/musa-helper:latest"

    output:
    path "ClinPred"

    script:
    """
    mkdir -p ClinPred
    cd ClinPred

    gdown --no-cookies --id 1e0kd9hO1uCEuGzAhwEmLCNluqDFJE28y

    awk '(\$2 == "Start" || \$2 ~ /^[0-9]+\$/){print \$0}' ClinPred_${params.build}.txt > ClinPred_${params.build}_tabbed.tsv
    sed -i '1s/.*/#&/' ClinPred_${params.build}_tabbed.tsv
    sed -i '1s/Chr/chr/' ClinPred_${params.build}_tabbed.tsv

    { head -n1 ClinPred_${params.build}_tabbed.tsv; tail -n +2 ClinPred_${params.build}_tabbed.tsv | sort -k1,1V -k2,2V; } > ClinPred_${params.build}_sorted_tabbed.tsv

    bgzip ClinPred_${params.build}_sorted_tabbed.tsv
    tabix -f -s 1 -b 2 -e 2 ClinPred_${params.build}_sorted_tabbed.tsv.gz

    cd ..
    """
}