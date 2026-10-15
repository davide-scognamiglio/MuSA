/*
 * MuSA
 * Module: DOWNLOAD_GNOMAD_EXOMES
 * Purpose: gnomAD v4.1 exomes allele counts for VEP --custom (the gnomADe41_* columns)
 *
 * The VEP cache carries gnomAD allele frequencies only, and dbNSFP's counts cover SNVs only, so
 * indels had no AN (no FAF95 can be computed) and no homozygote count. Ensembl's trimmed gnomAD
 * 4.1 exomes VCFs (one per chromosome, ~15 GB in all) keep AC, AN, AF and nhomalt overall, by sex
 * and by genetic-ancestry group, the grpmax group and gnomAD's own FAF95/FAF99, for every variant.
 */


process DOWNLOAD_GNOMAD_EXOMES {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('gnomad_exomes_manifest.yaml')

    script:
    def chroms = (1..22).collect { "chr${it}" } + ['chrX', 'chrY']
    def keys = chroms.collectMany { ["gnomad_exomes_${it}", "gnomad_exomes_${it}_tbi"] }.join(' ')
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "${keys}" "${changed_entries}" "/data/vep_data/gnomAD_exomes"; then
        echo "[INFO] No changes for download_gnomad_exomes -- skipping download, reusing existing data."
        cp "${manifest}" gnomad_exomes_manifest.yaml
        exit 0
    fi

    mkdir -p gnomAD_exomes
    cd gnomAD_exomes
    # Ensembl's FTP is slow per connection (~0.3-1 MB/s) and these are 48 files: download six at a
    # time, then record each SHA-256 one by one (write_computed_sha256 edits the manifest in place,
    # so it must not run concurrently). A checksum that differs from the manifest is not fatal: the
    # setup report marks it MISMATCH. A failed download is.
    for key in ${keys}; do
        url_var="\${key}_url"; method_var="\${key}_method"; out_var="\${key}_out"
        ( download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}" > "\${key}.sha" \
            || rm -f "\${key}.sha" ) &
        while [ "\$(jobs -rp | wc -l)" -ge 6 ]; do wait -n || true; done
    done
    wait || true
    for key in ${keys}; do
        out_var="\${key}_out"
        if [ ! -s "\${key}.sha" ]; then
            echo "[ERROR] \${!out_var}: download failed" >&2
            exit 1
        fi
        write_computed_sha256 "\$PWD/../${manifest}" "\$key" "\$(cat "\${key}.sha")"
        rm "\${key}.sha"
    done
    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "gnomAD_exomes" "/data/vep_data/gnomAD_exomes"

    mv ${manifest} gnomad_exomes_manifest.yaml
    """
}
