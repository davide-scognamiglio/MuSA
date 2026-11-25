/*
 * MuSA
 * Module: DOWNLOAD_REPEAT_REGIONS
 * Purpose: Download UCSC RepeatMasker (rmsk) and Tandem Repeats Finder (simpleRepeat) for hg38 and
 *          build the repeat-region BED that REPEAT_REGIONS reads
 *
 * Only the RepeatMasker classes describing tandem or repetitive sequence are kept (Simple_repeat,
 * Low_complexity, Satellite) plus every TRF interval; see bin/repeat_regions.py. UCSC serves both
 * files unversioned: the manifest records their date and checksum, and a different download is a
 * MISMATCH in the setup report, not a failure. The raw tables are not kept.
 */

process DOWNLOAD_REPEAT_REGIONS {
    tag "repeat_regions_setup"
    container "dsbioinfo/musa-helper:rebuild"
    memory { 4.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        file manifest
        path changed_entries

    output:
        file('repeat_regions_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "ucsc_rmsk ucsc_simple_repeat" "${changed_entries}" "/data/repeat_regions"; then
        echo "[INFO] No changes for download_repeat_regions -- skipping download, reusing existing data."
        cp "${manifest}" repeat_regions_manifest.yaml
        exit 0
    fi

    mkdir -p repeat_regions
    cd repeat_regions
    for key in ucsc_rmsk ucsc_simple_repeat; do
        url_var="\${key}_url"; method_var="\${key}_method"; out_var="\${key}_out"
        sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")
        write_computed_sha256 "\$PWD/../${manifest}" "\$key" "\$sha"
    done
    repeat_regions.py build "\${ucsc_rmsk_out}" "\${ucsc_simple_repeat_out}" repeat_regions.bed.gz
    rm "\${ucsc_rmsk_out}" "\${ucsc_simple_repeat_out}"
    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "repeat_regions" "/data/repeat_regions"

    mv ${manifest} repeat_regions_manifest.yaml
    """
}
