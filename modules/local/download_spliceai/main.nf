/*
 * MuSA
 * Module: DOWNLOAD_SPLICEAI
 * Purpose: SpliceAI precomputed splicing scores (VEP plugin SpliceAI)
 *
 * Ensembl's masked SNV scores for MANE transcripts (Illumina recommends the masked set for variant
 * interpretation: it hides gains of existing splice sites and losses of non-sites). Indel scores
 * exist only behind an Illumina BaseSpace login, so the plugin runs SNV-only: SpliceAI.pm opens an
 * indel file unconditionally ("No file specified" otherwise), so it gets a header-only one.
 */


process DOWNLOAD_SPLICEAI {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('spliceai_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_spliceai_snv vep_spliceai_snv_tbi" "${changed_entries}" "/data/vep_data/SpliceAI"; then
        echo "[INFO] No changes for download_spliceai -- skipping download, reusing existing data."
        cp "${manifest}" spliceai_manifest.yaml
        exit 0
    fi

    mkdir -p SpliceAI
    cd SpliceAI

    for key in vep_spliceai_snv vep_spliceai_snv_tbi; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    # The SNV file's header with no records: the indel file SpliceAI.pm insists on.
    tabix -H spliceai_scores.masked.snv.ensembl_mane_v1.4.grch38.vcf.gz | bgzip > spliceai_scores.none.indel.vcf.gz
    tabix -p vcf spliceai_scores.none.indel.vcf.gz

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "SpliceAI" "/data/vep_data/SpliceAI"

    mv ${manifest} spliceai_manifest.yaml
    """
}
