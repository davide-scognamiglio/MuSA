/*
 * MuSA
 * Module: DOWNLOAD_GENE_GFF3
 * Purpose: Ensembl gene models as GFF3, for the NearestGene plugin
 *
 * NearestGene needs an Ensembl database connection unless it reads gene locations from a
 * tabix-indexed GFF3; the release matches the VEP cache, so the nearest gene is one VEP knows.
 */


process DOWNLOAD_GENE_GFF3 {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('gene_gff3_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_gene_gff3" "${changed_entries}" "/data/vep_data/gene_gff3"; then
        echo "[INFO] No changes for download_gene_gff3 -- skipping download, reusing existing data."
        cp "${manifest}" gene_gff3_manifest.yaml
        exit 0
    fi

    mkdir -p gene_gff3
    cd gene_gff3

    for key in vep_gene_gff3; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    # Sort and index for tabix; NearestGene reads it with gff3=, which also lets it run offline.
    zcat Homo_sapiens.GRCh38.gff3.gz \\
        | awk '/^#/ { next } { print }' \\
        | LC_ALL=C sort -k1,1 -k4,4n -k5,5n \\
        | bgzip > genes.gff3.gz
    tabix -p gff genes.gff3.gz
    rm Homo_sapiens.GRCh38.gff3.gz

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "gene_gff3" "/data/vep_data/gene_gff3"

    mv ${manifest} gene_gff3_manifest.yaml
    """
}
