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
                panel       : row.panel,
                // Family and cohort modes (1.6): rows sharing a `group` are one joint-called VCF.
                group       : (row.group ?: '').trim(),
                sample      : (row.sample ?: '').trim(),
                role        : (row.role ?: '').trim().toLowerCase(),
                sex         : (row.sex ?: '').trim().toLowerCase(),
                affected    : (row.affected ?: '').trim().toLowerCase(),
                family      : (row.family ?: '').trim()
            ]
            [meta, row.sample_file]
        }
}

/*
 * Family and cohort modes. Rows with an empty `group` pass through unchanged (one patient, one
 * VCF, as before 1.6). Rows sharing a `group` become ONE item: the group's joint-called VCF, with
 * meta.patient = the group name (it names the output directory and files, as a patient does) and
 * meta.members = the rows, proband first. The mode is a family when any member is a proband,
 * mother or father, a cohort when every member is a `case`.
 *
 * Checks that would otherwise surface as a wrong answer much later: every member names its VCF
 * column (`sample`), all rows of a group point at the same VCF, a family has exactly one proband,
 * sexes and affected statuses are spelled as documented.
 */
def group_samples(ch_rows) {
    def FAMILY_ROLES = ['proband', 'mother', 'father', 'sibling', 'relative']
    def ROLES        = FAMILY_ROLES + ['case']
    def SEXES        = ['male', 'female', '', '.']
    def AFFECTED     = ['yes', 'no', '', '.']

    def singles = ch_rows.filter { meta, _vcf -> !meta.group }
    def grouped = ch_rows
        .filter { meta, _vcf -> meta.group }
        .map { meta, vcf -> [meta.group, meta, vcf] }
        .groupTuple()
        .map { group, metas, vcfs ->
            def where = "samplesheet group '${group}'"
            if (vcfs.unique(false).size() != 1) {
                error "${where}: every member must point at the same joint-called VCF (found ${vcfs.unique(false).join(', ')})"
            }
            metas.each { m ->
                if (!m.sample) error "${where}: member '${m.patient}' has no `sample` (its column name in the VCF)"
                if (!(m.role in ROLES)) error "${where}: member '${m.patient}' has role '${m.role}'; expected one of ${ROLES.join(', ')}"
                if (!(m.sex in SEXES)) error "${where}: member '${m.patient}' has sex '${m.sex}'; expected male, female or empty"
                if (!(m.affected in AFFECTED)) error "${where}: member '${m.patient}' has affected '${m.affected}'; expected yes, no or empty"
            }
            def samples = metas.collect { m -> m.sample }
            if (samples.unique(false).size() != samples.size()) error "${where}: a VCF sample is listed twice"
            def roles = metas.collect { m -> m.role }
            def is_family = roles.any { r -> r in FAMILY_ROLES }
            if (is_family && roles.contains('case')) error "${where}: mixes family roles and `case`; a group is either a family or a cohort"
            if (is_family && roles.count('proband') != 1) error "${where}: a family needs exactly one proband (found ${roles.count('proband')})"
            if (roles.count('mother') > 1 || roles.count('father') > 1) error "${where}: more than one mother or father"
            if (is_family && metas.find { m -> m.role == 'proband' }.sex in ['', '.']) {
                error "${where}: the proband's sex is needed for chrX and chrY inheritance"
            }
            // Proband first: the VCF is subset in this order, so the proband's genotype is the
            // one every single-sample step and column (Sample_*, Zygosity, the report) reads.
            def members = is_family ? metas.sort(false) { m -> m.role == 'proband' ? 0 : 1 } : metas
            // The phenotype searched for: every affected member's terms (family), every case's
            // terms (cohort); duplicates removed, order kept.
            def hpo = members
                .findAll { m -> is_family ? m.affected == 'yes' || m.role == 'proband' : true }
                .collectMany { m -> (m.hpo ?: '').tokenize(';') }
                .unique()
                .join(';')
            def meta = [
                patient     : group,
                group       : group,
                mode        : is_family ? 'family' : 'cohort',
                sample_type : members[0].sample_type,
                sample_file : members[0].sample_file,
                hpo         : hpo,
                panel       : members[0].panel,
                members     : members.collect { m -> m.subMap(['patient', 'sample', 'role', 'sex', 'affected', 'family', 'hpo']) }
            ]
            [meta, vcfs[0]]
        }
    return singles.map { meta, vcf -> [meta + [mode: 'single', members: []], vcf] }.mix(grouped)
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
