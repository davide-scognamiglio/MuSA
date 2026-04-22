/*
 * MuSA
 * Module: PARSE_VEP_ANNOTATION
 * Purpose: Parse VEP annotated VCF to extract relevant variant fields
 */


process PARSE_VEP_ANNOTATION {
    tag "parse-vep"
    cpus 1
    errorStrategy 'retry'
    maxRetries 3
    memory { 8.GB * task.attempt }

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.vep_parsed.tsv")

    script:
        """
        input="${vcf}"
        output="${meta.patient}.vep_parsed.tsv"

    awk '
    BEGIN {
        FS="\\t"; OFS="\\t"
        csq_format_found = 0
        n_info = 0
        after_csq = 0
    }

    # Capture CSQ field format
    /^##INFO=<ID=CSQ/ {
        if (match(\$0, /Format: (.*)">/, arr)) {
            n_csq = split(arr[1], csq_fields, "|")
            csq_format_found = 1
            after_csq = 1   # From now on, we treat INFO fields as "after CSQ"
        }
        next
    }

    # Capture INFO fields only AFTER CSQ definition
    /^##INFO=<ID=/ {
        if (match(\$0, /<ID=([^,]+)/, arr)) {
            id = arr[1]
            if (after_csq && id != "CSQ") {
                n_info++
                info_fields[n_info] = id
            }
        }
        next
    }

    /^##/ { next }

    # Header line
    /^#CHROM/ {
        printf "CHROM\\tPOS\\tID\\tREF\\tALT\\tQUAL\\tFILTER\\tbioinfo_params"

        # CSQ annotation columns
        if (csq_format_found)
            for (i=1; i<=n_csq; i++) printf "\\t%s", csq_fields[i]

        # Additional INFO fields (AFTER CSQ only)
        for (j=1; j<=n_info; j++) printf "\\t%s", info_fields[j]

        printf "\\tFORMAT_FIELDS\\tFORMAT_VALUES\\n"
        next
    }

    # Data lines
    !/^#/ {
        chrom=\$1; pos=\$2; id=\$3; ref=\$4; alt=\$5; qual=\$6; filter=\$7
        info=\$8; format=\$9; sample=\$10

        bioinfo_params = info
        annot_info = ""
        csq_part = ""

        # Split INFO into pre-CSQ and post-CSQ parts
        if (index(info, ";CSQ=") > 0) {
            split(info, parts, ";CSQ=")
            bioinfo_params = parts[1]
            annot_info = parts[2]
        }

        # Extract CSQ entry (the first section before any further ;)
        if (match(annot_info, /^[^;]+/, arr)) csq_part = arr[0]
        sub(/^.*CSQ=[^;]+;?/, "", annot_info)

        # Parse CSQ entries
        delete csq_data
        if (csq_format_found && csq_part != "") {
            split(csq_part, csq_data, "|")
            for (i in csq_data) gsub(/&/, ",", csq_data[i])
        }

        # Parse annotation INFO pairs (AFTER CSQ)
        delete info_pairs
        split(annot_info, annots, ";")
        for (i in annots) {
            if (annots[i] == "") continue
            split(annots[i], kv, "=")
            key = kv[1]
            val = (length(kv[2]) ? kv[2] : "TRUE")
            gsub(/&/, ",", val)
            info_pairs[key] = val
        }

        # FORMAT fields
        fmt_str = format
        val_str = sample
        gsub(/\\t/, "|", val_str)

        # Print row
        printf "%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s", chrom, pos, id, ref, alt, qual, filter, bioinfo_params

        if (csq_format_found)
            for (i=1; i<=n_csq; i++) {
                val = (i in csq_data) ? csq_data[i] : ""
                printf "\\t%s", val
            }

        for (j=1; j<=n_info; j++) {
            key = info_fields[j]
            val = (key in info_pairs) ? info_pairs[key] : ""
            printf "\\t%s", val
        }

        printf "\\t%s\\t%s\\n", fmt_str, val_str
    }
    ' "\$input" > "\$output"
    """
}