/*
 * MuSA
 * Module: DOWNLOAD_REFGENOME
 * Purpose: Download/create reference genome files
 */


process DOWNLOAD_REFGENOME{
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "reference_genome"
    container "dsbioinfo/gatk:latest"

    input:
        file manifest
        path changed_entries

    output:
        file('refGenome_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh
    parse_manifest "${manifest}"

    if should_skip_module "reference_genome" "${changed_entries}" "/data/vep_data/reference_genome"; then
        echo "[INFO] No changes for download_refgenome -- skipping download, reusing existing data."
        cp "${manifest}" refGenome_manifest.yaml
        exit 0
    fi

    mkdir reference_genome
    cd reference_genome

    sha=\$(download_and_compute_sha "\$reference_genome_url" "\$reference_genome_method" "\$reference_genome_out")
    write_computed_sha256 "../${manifest}" "reference_genome" \$sha


    # TODO: find a better soolution to not reference directly the ref genome build to construct the filenames
    # Create .dict using GATK (Picard)
    gunzip ${params.build}.fa.gz

    samtools faidx ${params.build}.fa

    gatk CreateSequenceDictionary \
       -R ${params.build}.fa \
       -O ${params.build}.dict

    cd ..

    mv ${manifest} refGenome_manifest.yaml
    
    """
}