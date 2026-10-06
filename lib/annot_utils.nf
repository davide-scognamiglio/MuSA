// workflows/lib/annot_utils.nf

def extract_csv(csv_file) {
    // A samplesheet is a handful of lines, so reading it whole is fine. (Nextflow's strict syntax,
    // the default from 26.04, has no `while` loop to stream it line by line.)
    def lines = file(csv_file).readLines()
    if (lines.size() >= 1) {
        def requiredColumns = ["patient", "sample_type", "sample_file", "hpo"]
        if (!requiredColumns.every { lines[0].contains(it) }) {
            error "Samplesheet is missing required columns: ${requiredColumns}"
        }
    }
    if (lines.size() == 1) {
        error "Samplesheet contains a header but no samples: provide at least one sample."
    }

    return Channel.from(csv_file)
        .splitCsv(header:true)
        .map { row ->
            def meta = [
                patient     : row.patient,
                sample_type : row.sample_type,
                sample_file : row.sample_file,
                hpo         : row.hpo,
                panel       : row.panel
            ]
            [meta, row.sample_file]
        }
}

def chrom_list(fai_path) {
    file(fai_path).readLines()
        .collect { it.split('\t')[0] }
        .findAll { it ==~ /chr([1-9]|1[0-9]|2[0-2]|X|Y|M)/ }
}

/*
 * The annotation sources this run uses, read from assets/annotation_sources.yaml (the single list
 * the README, docs/sources.md and the report are generated from) and resolved against the
 * installed data directory: each source gets the version its manifest entry records (or the install
 * date of its file when the entry has none) and whether this run's mode turns it on.
 */
def annotation_sources() {
    def yaml = new org.yaml.snakeyaml.Yaml()
    def catalogue = yaml.load(file("${projectDir}/assets/annotation_sources.yaml").text)
    def manifestFile = file("${params.data_dir}/dbs_manifest.yaml")
    def installed = manifestFile.exists()
        ? ((yaml.load(manifestFile.text) ?: [:])[params.build_alt_name.toLowerCase()] ?: [:])
        : [:]

    return catalogue.sources.collect { s ->
        def p = catalogue.providers[s.provider]
        def mode = s.mode ?: p.mode
        [
            id      : s.id,
            name    : s.name,
            what    : s.what,
            level   : s.level,
            category: s.category,
            kind    : s.kind ?: 'resource',
            mode    : mode,
            active  : source_active(mode, s.provider),
            provider: s.plugin ? "VEP plugin ${s.plugin}" : p.name,
            step    : p.step,
            version : source_version(installed, s.manifest ?: p.manifest, s.manifest ? null : p.data, p.version),
            url     : p.url,
        ]
    }
}

// Manifest version, else the install date of the source's file, else the version the pipeline
// fixes itself (a container tag or a params value).
def source_version(installed, key, dataPath, fixed) {
    def v = key ? installed[key]?.version?.toString() : null
    if (v && v != '-') {
        return v
    }
    if (dataPath) {
        def f = file("${params.data_dir}/${dataPath}")
        if (f.exists()) {
            return "installed " + new Date(f.lastModified()).format('yyyy-MM-dd')
        }
    }
    if (fixed && fixed.startsWith('params.')) {
        return params[fixed.substring(7)]?.toString()?.tokenize(':')?.last()
    }
    return fixed ? fixed.replaceFirst(/^container /, '') : ''
}

def source_active(mode, providerId) {
    def extended = params.extended as boolean
    def online = !params.offline && !(providerId == 'genebe' && params.skip_genebe)
    if (mode == 'extended') {
        return extended
    }
    if (mode == 'online') {
        return online
    }
    if (mode == 'extended+online') {
        return extended && online
    }
    return true
}

// What turns a source of the given mode on, for the "[off: ...]" hint.
def mode_switch(mode) {
    return [extended: '--extended true', online: '--offline false',
            'extended+online': '--extended true --offline false'][mode]
}

// The start-of-run block that says, step by step, which sources this run annotates from.
def log_annotation_sources(sources) {
    def counted = sources.findAll { s -> s.kind == 'resource' && s.level != 'format' }
    def lines = [
        "",
        "──────────────────── Annotation sources ────────────────────",
        "${counted.count { s -> s.active }} of ${counted.size()} sources active in this run " +
            "(full list with columns: docs/sources.md)",
    ]
    counted.groupBy { s -> s.step }.each { step, group ->
        lines << ""
        lines << "  ${step}"
        group.groupBy { s -> [s.provider, s.version, s.active, s.mode] }.each { key, items ->
            def status = key[2] ? '' : "  [off: ${mode_switch(key[3])}]"
            lines << "    ${key[0]}${key[1] ? ' ' + key[1] : ''}${status}"
            lines.addAll(wrap_names(items.collect { s -> s.name }, '      ', 92))
        }
    }
    lines << "─────────────────────────────────────────────────────────────"
    log.info lines.join('\n')
}

// Comma-separated names wrapped at `width` columns, each line starting with `indent`.
def wrap_names(names, indent, width) {
    def out = []
    def row = ''
    names.each { n ->
        if (row && (indent + row + ', ' + n).length() > width) {
            out << indent + row
            row = n
        } else {
            row = row ? row + ', ' + n : n
        }
    }
    if (row) {
        out << indent + row
    }
    return out
}
