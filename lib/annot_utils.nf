// workflows/lib/annot_utils.nf

def extract_csv(csv_file) {
    file(csv_file).withReader('UTF-8') { reader ->
        def n = 0
        while ((line = reader.readLine()) != null) {
            n++
            if (n==1) {
                def requiredColumns = ["patient", "sample_type", "sample_file", "hpo"]
                if (!requiredColumns.every { line.contains(it) }) {
                    log.error "Missing required columns: ${requiredColumns}"
                    System.exit(1)
                }
            }
        }
        if (n==1) {
            log.error "Provide at least one sample."
            System.exit(1)
        }
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
