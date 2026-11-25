/*
 * MuSA
 * Module: SELECT_MEMBERS
 * Purpose: Keep only the group's members from a joint-called VCF, in samplesheet order (proband
 *          first), and only the sites and alternate alleles at least one of them carries.
 *
 * A joint VCF often holds a whole cohort; a family is annotated on its own members' variants.
 * Proband first is the order every later step expects. PARSE_VEP_ANNOTATION reads the members by
 * name, which survives any step that reorders the columns (GATK sorts them by name;
 * GATK_VARIANTFILTRATION_HARDFILTER puts them back). bcftools 1.2 keeps the file's sample order
 * under `-s`, hence the explicit reorder here.
 *
 * Also used for a single patient whose samplesheet row names a `sample` in a multi-sample VCF.
 */

process SELECT_MEMBERS {
    tag "${meta.patient} | ${meta.members ? meta.members.size() : 1} sample(s)"
    container "dsbioinfo/bcftools:1.2"
    memory { 2.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 2

    input:
        tuple val(meta), path(vcf)

    output:
        tuple val(meta), path("members.vcf")

    script:
        def list = (meta.members ? meta.members.collect { m -> m.sample } : [meta.sample]).join(',')
        """
        set -euo pipefail

        missing=\$(bcftools query -l ${vcf} | awk -v want="${list}" '
            BEGIN { n = split(want, w, ","); for (i = 1; i <= n; i++) need[w[i]] = 1 }
            { delete need[\$1] }
            END { for (s in need) printf "%s ", s }')
        if [ -n "\$missing" ]; then
            echo "[ERROR] ${meta.patient}: sample(s) not in ${vcf}: \$missing" >&2
            exit 1
        fi

        # -c 1: at least one alternate allele among the members; -a: drop alternate alleles none of
        # them carries, so a cohort-wide multiallelic site becomes the members' own alleles.
        bcftools view -s "${list}" -c 1 -a ${vcf} -Ov \\
          | awk -F'\\t' -v OFS='\\t' -v want="${list}" '
              /^##/ { print; next }
              /^#CHROM/ {
                  n = split(want, w, ",")
                  for (i = 10; i <= NF; i++) at[\$i] = i
                  for (i = 1; i <= n; i++) src[i] = at[w[i]]
              }
              {
                  line = \$1
                  for (i = 2; i <= 9; i++) line = line OFS \$i
                  for (i = 1; i <= n; i++) line = line OFS \$(src[i])
                  print line
              }' > members.vcf
        """
}
