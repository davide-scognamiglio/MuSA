// workflows/lib/annot_utils.nf

def extract_csv(csv_file) {
    // A samplesheet is a handful of lines, so reading it whole is fine. (Nextflow's strict syntax,
    // the default from 26.04, has no `while` loop to stream it line by line.)
    // `error` rather than System.exit(1): exiting the JVM directly orphaned tasks already dispatched.
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
