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
