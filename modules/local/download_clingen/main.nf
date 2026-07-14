/*
 * MuSA
 * Module: DOWNLOAD_CLINGEN
 * Purpose: Download the curated ClinGen resources used for annotation.
 *          Gene-level tables (installed raw under /data/clingen):
 *            - clingen_gene_dosage        : ClinGen_gene_curation_list (HI/TS)
 *            - clingen_gene_validity      : Gene-Disease Validity CSV
 *            - clingen_actionability_adult / _pediatric : Clinical Actionability
 *          Variant-level (built into a VEP --custom VCF, like ClinVar):
 *            - clingen_variant_path       : ERepo tabbed export -> pathogenicity VCF
 *
 * NOTE ON INSTALL: data_dir is bind-mounted rw at /data. We install straight into /data
 * (not via publishDir) — same rationale as DOWNLOAD_CLINVAR (nested-path publishDir fails).
 */


process DOWNLOAD_CLINGEN {
    tag "clingen_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('clingen_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh
    parse_manifest "${manifest}"

    gene_dir="/data/clingen"
    vcf_dir="/data/vep_data/ClinGen"
    dosage_target="\${gene_dir}/clingen_gene_dosage.tsv"

    if should_skip_module "clingen_gene_dosage clingen_gene_validity clingen_actionability_adult clingen_actionability_pediatric clingen_variant_path" "${changed_entries}" "\$dosage_target"; then
        echo "[INFO] No changes for download_clingen -- skipping download, reusing existing data."
        cp "${manifest}" clingen_manifest.yaml
        exit 0
    fi

    mkdir -p "\$gene_dir" "\$vcf_dir"

    # ---- Gene-level tables: download, hash, install under fixed names ----
    sha=\$(download_and_compute_sha "\$clingen_gene_dosage_url" "\$clingen_gene_dosage_method" "\$clingen_gene_dosage_out")
    write_computed_sha256 "${manifest}" "clingen_gene_dosage" \$sha
    cp -f "\$clingen_gene_dosage_out" "\${gene_dir}/clingen_gene_dosage.tsv"

    sha=\$(download_and_compute_sha "\$clingen_gene_validity_url" "\$clingen_gene_validity_method" "\$clingen_gene_validity_out")
    write_computed_sha256 "${manifest}" "clingen_gene_validity" \$sha
    cp -f "\$clingen_gene_validity_out" "\${gene_dir}/clingen_gene_validity.csv"

    sha=\$(download_and_compute_sha "\$clingen_actionability_adult_url" "\$clingen_actionability_adult_method" "\$clingen_actionability_adult_out")
    write_computed_sha256 "${manifest}" "clingen_actionability_adult" \$sha
    cp -f "\$clingen_actionability_adult_out" "\${gene_dir}/clingen_actionability_adult.tsv"

    sha=\$(download_and_compute_sha "\$clingen_actionability_pediatric_url" "\$clingen_actionability_pediatric_method" "\$clingen_actionability_pediatric_out")
    write_computed_sha256 "${manifest}" "clingen_actionability_pediatric" \$sha
    cp -f "\$clingen_actionability_pediatric_out" "\${gene_dir}/clingen_actionability_pediatric.tsv"

    # ---- Variant-level: ERepo export -> pathogenicity VCF -> bgzip + tabix ----
    sha=\$(download_and_compute_sha "\$clingen_variant_path_url" "\$clingen_variant_path_method" "\$clingen_variant_path_out")
    write_computed_sha256 "${manifest}" "clingen_variant_path" \$sha

    build_clingen_vcf.py --input "\$clingen_variant_path_out" --output clingen_pathogenicity.vcf
    # Records are emitted chr-prefixed (matching hg38.fa) and coordinate-sorted.
    bgzip -f clingen_pathogenicity.vcf
    tabix -p vcf clingen_pathogenicity.vcf.gz
    cp -f clingen_pathogenicity.vcf.gz     "\${vcf_dir}/clingen_pathogenicity.vcf.gz"
    cp -f clingen_pathogenicity.vcf.gz.tbi "\${vcf_dir}/clingen_pathogenicity.vcf.gz.tbi"

    mv ${manifest} clingen_manifest.yaml
    """
}
