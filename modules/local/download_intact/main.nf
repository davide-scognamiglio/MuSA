/*
 * MuSA
 * Module: DOWNLOAD_INTACT
 * Purpose: IntAct molecular interactions affected by mutations (VEP plugin IntAct)
 *
 * The genomic mapping file is published unsorted, uncompressed and for every species IntAct
 * curates; the plugin needs the human rows sorted, bgzipped and tabix-indexed.
 */


process DOWNLOAD_INTACT {
    tag "vep_setup"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest
        path changed_entries

    output:
        file('intact_manifest.yaml')

    script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    if should_skip_module "vep_intact_mutations vep_intact_mapping" "${changed_entries}" "/data/vep_data/IntAct"; then
        echo "[INFO] No changes for download_intact -- skipping download, reusing existing data."
        cp "${manifest}" intact_manifest.yaml
        exit 0
    fi

    mkdir -p IntAct
    cd IntAct

    for key in vep_intact_mutations vep_intact_mapping; do
        fetch_entry "\$PWD/../${manifest}" "\$key"
    done

    # IntAct.pm's recipe, with two changes. The file covers every species IntAct curates (mouse,
    # yeast, zebrafish ...) on their own chromosome names, which tabix would then match against
    # human positions: keep human (taxonomy 9606) on the primary chromosomes only. And sort with
    # LC_ALL=C below the header, or the locale sorts the "#chromosome" header among the rows and
    # tabix refuses the file ("chromosome blocks not continuous").
    {
        grep -m1 '^chromosome' mutation_gc_map.txt | sed 's/^/#/'
        awk -F'\\t' 'BEGIN { OFS = "\\t" }
            \$14 + 0 == 9606 && \$1 ~ /^([0-9]+|X|Y|Mitochondrion)\$/ {
                if (\$1 == "Mitochondrion") \$1 = "MT"
                if (\$2 > \$3) { a = \$2; \$2 = \$3; \$3 = a }
                print
            }' mutation_gc_map.txt \\
            | LC_ALL=C sort -k1,1 -k2,2n -k3,3n
    } | bgzip > mutation_gc_map.txt.gz
    tabix -s 1 -b 2 -e 3 -f mutation_gc_map.txt.gz
    rm mutation_gc_map.txt

    cd ..

    # Install into the data dir (bind-mounted at /data); see install_into_data in
    # bin/download_and_hash.sh for why this is not publishDir.
    install_into_data "IntAct" "/data/vep_data/IntAct"

    mv ${manifest} intact_manifest.yaml
    """
}
