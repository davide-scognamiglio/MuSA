#!/usr/bin/env bash
# Usage: ./add_genome_change.sh input.maf output.maf

input="$1"
output="$2"

if [[ -z "$input" || -z "$output" ]]; then
    echo "Usage: $0 input.maf output.maf"
    exit 1
fi

awk -F'\t' -v OFS='\t' '
NR==1 {
    # find columns of interest
    for (i=1; i<=NF; i++) {
        if ($i == "Chromosome") chr=i
        else if ($i == "Start_Position") start=i
        else if ($i == "End_Position") end=i
        else if ($i == "Reference_Allele") ref=i
        else if ($i == "Tumor_Seq_Allele2") alt=i
    }
    if (!(chr && start && end && ref && alt)) {
        print "Error: missing required columns in MAF header" > "/dev/stderr"
        exit 1
    }
    # print header + new column
    print $0, "genome_change"
    next
}
{
    c=$chr; s=$start; e=$end; r=$ref; a=$alt
    if (a == "-") {
        gc="g." c ":" s "_" e "del" r
    } else if (r == "-") {
        gc="g." c ":" s "_" e "ins" a
    } else if (s == e) {
        gc="g." c ":" s r ">" a
    } else {
        gc="g." c ":" s "_" e r ">" a
    }
    print $0, gc
}' "$input" > "$output"
