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
write_computed_sha256() {
    local yaml_file="$1"
    local entry_key="$2"   # original YAML key, e.g. "ANNOVAR_avsnp150"
    local sha_value="$3"

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
    { print }
    ' "$yaml_file" > "${yaml_file}.tmp" && mv "${yaml_file}.tmp" "$yaml_file"
}
