parse_manifest() {
    local yaml_file="$1"
    local genome="${2:-grch38}"

    [[ ! -f "$yaml_file" ]] && { echo "ERROR: file not found: $yaml_file" >&2; return 1; }

    local tmp_awk
    tmp_awk=$(mktemp /tmp/manifest_parser_XXXXXX.awk)

    cat > "$tmp_awk" << 'EOF'
function trim(s)    { gsub(/^[[:space:]]+|[[:space:]]+$/, "", s); return s }
function unquote(s) { gsub(/^"|"$/, "", s); return s }
function varname(s,   r) {
    r = tolower(s)
    gsub(/[^a-z0-9]+/, "_", r)
    gsub(/^_+|_+$/, "", r)
    return r
}
function flush_entry(   f, prefix, vn, v) {
    if (entry == "") return
    prefix = varname(entry)
    # ── store the original YAML key so we can map back later ──
    print prefix "_key='" entry "'"
    for (f in F) {
        vn = prefix "_" varname(f)
        v  = F[f]
        gsub(/'/, "'\\''", v)
        print vn "='" v "'"
    }
    delete F
    entry = ""
}

BEGIN { in_genome = 0; entry = "" }

/^[^[:space:]]/ {
    k = $0; sub(/:.*$/, "", k); k = trim(k)
    in_genome = (k == genome)
    flush_entry()
    next
}

in_genome && /^  [^[:space:]]/ {
    flush_entry()
    k = $0; sub(/^  /, "", k); sub(/:.*$/, "", k)
    entry = trim(k)
    next
}

in_genome && entry != "" && /^    [^[:space:]]/ {
    line = $0; sub(/^    /, "", line)
    colon = index(line, ": ")
    if (colon > 0) {
        k = substr(line, 1, colon - 1)
        v = unquote(substr(line, colon + 2))
        F[trim(k)] = v
    }
    next
}

END { flush_entry() }
EOF

    eval "$(awk -v genome="$genome" -f "$tmp_awk" "$yaml_file")"
    local rc=$?
    rm -f "$tmp_awk"
    return $rc
}

# should_skip_module <space-separated manifest entry keys> <changed_entries_file> <target_path_on_disk>
# Returns 0 (skip download) only if: not the "no update-db" NO_FILE sentinel,
# the target already exists on disk, AND every given key is absent from changed_entries_file.
should_skip_module() {
    local keys="$1"
    local changed_entries_file="$2"
    local target_path="$3"

    [[ "$(basename "$changed_entries_file")" == "NO_FILE" ]] && return 1
    [[ -e "$target_path" ]] || return 1

    local key
    for key in $keys; do
        grep -qxF "$key" "$changed_entries_file" && return 1
    done

    return 0
}

write_computed_sha256() {
    local yaml_file="$1"
    local entry_key="$2"   # original YAML key, e.g. "ANNOVAR_avsnp150"
    local sha_value="$3"

    # Writes computed_sha256 for the entry. Trust-on-first-use: if the entry's
    # expected_sha256 is currently empty (no known-good baseline, e.g. a freshly
    # added DB version), adopt this computed hash as the expected baseline too.
    awk -v entry="$entry_key" -v sha="$sha_value" '
    /^  [^[:space:]]/ {
        current = $0
        sub(/^  /, "", current)
        sub(/:.*$/, "", current)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", current)
        in_entry = (current == entry)
    }
    in_entry && /^    computed_sha256:/ {
        print "    computed_sha256: \"" sha "\""
        next
    }
    in_entry && /^    expected_sha256:/ {
        val = $0
        sub(/^    expected_sha256:[[:space:]]*/, "", val)
        gsub(/^"|"$/, "", val)
        gsub(/[[:space:]]/, "", val)
        if (val == "") {
            print "    expected_sha256: \"" sha "\""
        } else {
            print
        }
        next
    }
    { print }
    ' "$yaml_file" > "${yaml_file}.tmp" && mv "${yaml_file}.tmp" "$yaml_file"
}
