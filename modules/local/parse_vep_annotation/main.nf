/*
 * MuSA
 * Module: PARSE_VEP_ANNOTATION
 * Purpose: Parse VEP annotated VCF to extract relevant variant fields
 */


process PARSE_VEP_ANNOTATION {
    tag "parse-vep"
        cpus params.n_core
    errorStrategy 'retry'
    maxRetries 3
    memory { 8.GB * task.attempt }
    container "dsbioinfo/musa-helper:rebuild"

    input:
        tuple val(meta), file(vcf)

    output:
        tuple val(meta), file("${meta.patient}.vep_parsed.tsv")

    script:
        // The samples to read, by name, in the order the rest of the pipeline expects: a group's
        // members as in meta.members (proband first), or the row's own `sample` in a multi-sample VCF.
        def members = (meta.members ? meta.members.collect { m -> m.sample } : (meta.sample ? [meta.sample] : [])).join(',')
        """
        set -euo pipefail
        input="${vcf}"
        output="${meta.patient}.vep_parsed.tsv"

    # POSIX awk only: the helper image ships mawk, and so does a stock Ubuntu host. gawk extensions
    # such as match() with a capture array fail there with a syntax error.
    awk -v prefer="${meta.mode == 'family' ? meta.members[0].sample : ''}" -v members="${members}" '
    BEGIN {
        FS="\\t"; OFS="\\t"
        csq_format_found = 0
        n_info = 0
        after_csq = 0
    }

    # Capture CSQ field format
    /^##INFO=<ID=CSQ/ {
        if (match(\$0, /Format: .*">/)) {
            n_csq = split(substr(\$0, RSTART + 8, RLENGTH - 10), csq_fields, "|")
            csq_format_found = 1
            after_csq = 1   # From now on, we treat INFO fields as "after CSQ"
        }
        next
    }

    # Capture INFO fields only AFTER CSQ definition
    /^##INFO=<ID=/ {
        if (match(\$0, /<ID=[^,]+/)) {
            id = substr(\$0, RSTART + 4, RLENGTH - 4)
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

        # A family or cohort VCF has several sample columns. FORMAT_VALUES is the proband (or the
        # row sample); GROUP_FORMAT_VALUES holds the values of every member, in meta.members order and
        # space-separated (FORMAT values contain no spaces), so SAMPLE_GENOTYPES and GROUP_GENOTYPES
        # can expand them without one MAF column per member travelling through every step.
        # Members are found by NAME in this header, never by position: SELECT_MEMBERS writes them
        # proband first, but a later step may reorder the columns (GATK VariantFiltration and
        # SelectVariants sort them by name), and reading by position then gave one member the
        # genotypes of another. A member missing from the header stops the run.
        n_samples = NF - 9
        n_mem = (members != "") ? split(members, mem, ",") : 0
        for (i = 10; i <= NF; i++) at[\$i] = i
        for (i = 1; i <= n_mem; i++) {
            if (!(mem[i] in at)) {
                hdr_samples = ""
                for (k = 10; k <= NF; k++) hdr_samples = hdr_samples (k > 10 ? "," : "") \$k
                printf "[ERROR] PARSE_VEP_ANNOTATION: sample %s is not in the VCF header (samples: %s)\\n", mem[i], hdr_samples > "/dev/stderr"
                failed = 1
                exit 1
            }
            src[i] = at[mem[i]]
        }
        if (n_mem == 0) { n_mem = n_samples; for (i = 1; i <= n_mem; i++) src[i] = 9 + i }
        for (i=1; i<=n_csq; i++) {
            if (csq_fields[i] == "IND") i_ind = i
            if (csq_fields[i] == "ZYG") i_zyg = i
        }
        printf "\\tFORMAT_FIELDS\\tFORMAT_VALUES%s\\n", (n_samples > 1 ? "\\tGROUP_FORMAT_VALUES" : "")
        next
    }

    # Data lines
    !/^#/ {
        chrom=\$1; pos=\$2; id=\$3; ref=\$4; alt=\$5; qual=\$6; filter=\$7
        info=\$8; format=\$9; sample=\$(src[1])

        bioinfo_params = info
        annot_info = ""
        csq_part = ""

        # Split INFO into pre-CSQ and post-CSQ parts. CSQ may be preceded by other INFO fields
        # (leading semicolon before CSQ=) OR be the very first/only INFO field with no leading
        # semicolon, which is what VEP emits when the input VCF has an empty INFO column. Handle
        # both, else the whole CSQ blob stays in bioinfo_params and Consequence, IMPACT, etc. come
        # out NA. (NB: no apostrophes in this comment; the awk program is single-quoted in the
        # shell, so an embedded single quote would truncate it.)
        if (index(info, ";CSQ=") > 0) {
            split(info, parts, ";CSQ=")
            bioinfo_params = parts[1]
            annot_info = parts[2]
        } else if (index(info, "CSQ=") == 1) {
            bioinfo_params = ""
            annot_info = substr(info, 5)
        }

        # Extract CSQ entry (the first section before any further ;)
        if (match(annot_info, /^[^;]+/)) csq_part = substr(annot_info, RSTART, RLENGTH)
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

        # In a family or cohort VCF, G2P switches on VEP per-individual output: one record per member
        # carrying the variant, identical apart from IND and ZYG. One row per variant is kept, the
        # proband copy when there is one; IND and ZYG are blanked when they describe someone else
        # (Zygosity and Sample_* hold the proband call).
        if (n_samples > 1 && (i_ind in csq_data) && csq_data[i_ind] != prefer) {
            csq_data[i_ind] = ""
            if (i_zyg in csq_data) csq_data[i_zyg] = ""
        }
        is_pref = (n_samples > 1 && prefer != "" && (i_ind in csq_data) && csq_data[i_ind] == prefer)

        row = chrom "\\t" pos "\\t" id "\\t" ref "\\t" alt "\\t" qual "\\t" filter "\\t" bioinfo_params
        if (csq_format_found)
            for (i=1; i<=n_csq; i++) row = row "\\t" ((i in csq_data) ? csq_data[i] : "")
        for (j=1; j<=n_info; j++) {
            key = info_fields[j]
            row = row "\\t" ((key in info_pairs) ? info_pairs[key] : "")
        }
        row = row "\\t" fmt_str "\\t" val_str
        if (n_samples > 1) {
            group_str = \$(src[1])
            for (k = 2; k <= n_mem; k++) group_str = group_str " " \$(src[k])
            row = row "\\t" group_str
        }

        site = chrom SUBSEP pos SUBSEP ref SUBSEP alt
        if (n_samples > 1 && site == pending_site) {
            if (is_pref && !pending_pref) { pending = row; pending_pref = 1 }
            next
        }
        if (pending_site != "") print pending
        pending = row; pending_site = site; pending_pref = is_pref
    }

    END { if (!failed && pending_site != "") print pending }
    ' "\$input" > "\$output"
    """
}