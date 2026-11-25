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

    # A module that skipped its download (--update_db_only, entry unchanged) hands back the new
    # manifest, whose computed_sha256 is empty, so an upgrade used to forget every checksum it
    # did not recompute: the setup report showed files verified by an earlier setup as PENDING.
    # The data directory's current manifest still holds them; one is carried over only when the
    # entry's url and expected_sha256 are the same in both, i.e. the same file is installed.
    if [[ -f /data/dbs_manifest.yaml ]]; then
        entries() {
            awk '
                function val(s) { sub(/^[^:]*:[[:space:]]*/, "", s); gsub(/^"|"\$/, "", s); return s }
                function flush() { if (entry != "") print entry "\\t" url "\\t" expected "\\t" computed }
                /^  [^[:space:]#]/ { flush(); entry = \$0; sub(/^  /, "", entry); sub(/:.*\$/, "", entry)
                                     url = expected = computed = ""; next }
                /^    url:/             { url = val(\$0) }
                /^    expected_sha256:/ { expected = val(\$0) }
                /^    computed_sha256:/ { computed = val(\$0) }
                END { flush() }
            ' "\$1"
        }
        entries /data/dbs_manifest.yaml > old_entries.tsv
        entries merged.yaml | while IFS=\$'\\t' read -r key url expected computed; do
            [[ -n "\$computed" ]] && continue
            old=\$(awk -F'\\t' -v k="\$key" -v u="\$url" -v e="\$expected" \\
                '\$1 == k && \$2 == u && \$3 == e && \$4 != "" { print \$4; exit }' old_entries.tsv)
            [[ -n "\$old" ]] && write_computed_sha256 merged.yaml "\$key" "\$old"
        done
    fi
    """
}