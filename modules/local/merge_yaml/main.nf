/*
 * MuSA
 * Module: MERGE_YAML
 * Purpose: Merge yaml into a single yaml
 */

process MERGE_YAML {
    tag "merge-annotations"
    cpus params.n_core
    memory { 8.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 3
    container "dsbioinfo/musa-helper:rebuild"
    publishDir "${params.data_dir}", mode: 'copy', overwrite: true, saveAs: { filename -> filename == "merged.yaml" ? "dbs_manifest.yaml" : null }

    input:
    path(yamls)

    output:
    file("merged.yaml")

    script:
    """
    set -euo pipefail
    source manifest_parser.sh

    # Convert the space-separated Nextflow path list into a bash array
    yaml_array=( ${yamls} )

    # Use the first yaml as the structural base
    cp "\${yaml_array[0]}" merged.yaml

    # Iterate over all yamls (including the first, harmless to re-apply)
    for partial in "\${yaml_array[@]}"; do
        [[ ! -f "\$partial" ]] && continue

        awk '
            /^  [^[:space:]]/ {
                current = \$0
                sub(/^  /, "", current)
                sub(/:.*\$/, "", current)
                gsub(/^[[:space:]]+|[[:space:]]+\$/, "", current)
                entry = current
                sha = ""
            }
            /^    computed_sha256:/ {
                val = \$0
                sub(/^    computed_sha256:[[:space:]]*/, "", val)
                gsub(/^"|"\$/, "", val)
                gsub(/^'"'"'|'"'"'\$/, "", val)
                if (val != "" && entry != "") {
                    print entry "\\t" val
                }
            }
        ' "\$partial" | while IFS=\$'\\t' read -r entry_key sha_value; do
            write_computed_sha256 merged.yaml "\$entry_key" "\$sha_value"
        done
    done
    """
}