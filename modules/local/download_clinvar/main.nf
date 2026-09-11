/*
 * MuSA
 * Module: DOWNLOAD_CLINVAR
 * Purpose: Download a self-managed ClinVar VCF (+ .tbi) for use as a VEP --custom annotation.
 *          This decouples ClinVar from the VEP cache / dbNSFP / ANNOVAR so the exact release is
 *          curated via the manifest (entries: `clinvar` = vcf.gz, `clinvar_tbi` = index).
 *
 * NOTE ON INSTALL: the data_dir is bind-mounted rw at /data (see nextflow.config docker/podman/
 * singularity containerOptions, --user root). We install straight into /data — NOT via publishDir —
 * because publishDir with a nested-path pattern silently fails to publish the tree (the vep_cache
 * module hit exactly that, leaving the download stranded in the work dir).
 */


process DOWNLOAD_CLINVAR {
    tag "clinvar_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('clinvar_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh
    parse_manifest "${manifest}"

    target_dir="/data/vep_data/ClinVar"
    target_vcf="\${target_dir}/clinvar.vcf.gz"

    if should_skip_module "clinvar clinvar_tbi" "${changed_entries}" "\$target_vcf"; then
        echo "[INFO] No changes for download_clinvar -- skipping download, reusing existing data."
        cp "${manifest}" clinvar_manifest.yaml
        exit 0
    fi

    echo "Downloading self-managed ClinVar VCF (\${clinvar_out}) + index..."

    # Download the VCF + its tabix index into the work dir, verify each, record computed hashes.
    sha=\$(download_and_compute_sha "\$clinvar_url" "\$clinvar_method" "\$clinvar_out")
    write_computed_sha256 "${manifest}" "clinvar" \$sha

    sha_tbi=\$(download_and_compute_sha "\$clinvar_tbi_url" "\$clinvar_tbi_method" "\$clinvar_tbi_out")
    write_computed_sha256 "${manifest}" "clinvar_tbi" \$sha_tbi

    # The NCBI ClinVar VCF uses Ensembl-style contigs (1,2,...,MT); this pipeline is chr-prefixed
    # (NORMALIZE_CHR -> chr1..chrM, matching the hg38.fa reference). VEP --custom type=exact matches
    # by contig name, so rewrite ClinVar's contigs to match EXACTLY (mirrors NORMALIZE_CHR: MT->chrM,
    # else prepend chr), then re-index. Without this, --custom matches zero records (all CLNSIG empty).
    zcat "\$clinvar_out" | awk 'BEGIN{FS=OFS="\\t"}
        /^##contig=<ID=/ { if (\$0 ~ /<ID=MT[,>]/) sub(/<ID=MT/,"<ID=chrM"); else sub(/<ID=/,"<ID=chr"); print; next }
        /^#/ { print; next }
        { if (\$1=="MT") \$1="chrM"; else if (\$1 !~ /^chr/) \$1="chr" \$1; print }
    ' | bgzip > clinvar.vcf.gz
    tabix -p vcf clinvar.vcf.gz

    # Install into the mounted data_dir under FIXED names so the VEP --custom path is stable
    # regardless of the dated release in the manifest.
    mkdir -p "\$target_dir"
    cp -f clinvar.vcf.gz     "\${target_dir}/clinvar.vcf.gz"
    cp -f clinvar.vcf.gz.tbi "\${target_dir}/clinvar.vcf.gz.tbi"

    mv ${manifest} clinvar_manifest.yaml
    """
}
