/*
 * MuSA
 * Module: SPLIT_VCF_BY_CHR
 * Purpose: Split a VCF into one shard per chromosome in a single pass (dbNSFP per-chromosome scatter)
 */

/*
 * One task per VCF, not one per (VCF x chromosome). The previous shape was
 * `SPLIT_VCF_BY_CHR(vcf.combine(chr_ch))`, which on the 147-chunk ClinVar run meant 3,675 containers
 * each running one `bcftools view -t chrN` across the whole file: every chunk was read 25 times to do
 * a measured 19ms of work, and the shards trickled out over 37 minutes, holding dbNSFP back. A single
 * awk pass writes every shard at once.
 *
 * `chrs` carries the same chrom_list() the cartesian product used to supply, and shards are emitted
 * only for those chromosomes. That filter is load-bearing, not decoration: a Sarek VCF also contains
 * alt/random/decoy contigs, and dbNSFP has no per-chromosome database for them.
 *
 * Only chromosomes actually carrying records get a shard, which is safe by construction:
 * GATHER_DBNSFP_TSV skips empty inputs and DBNSFP_ANNOTATE_VCF_CHR keeps its own empty-shard guard.
 *
 * awk rather than `bcftools +scatter`: this image is bcftools 1.2 (2015); +scatter arrived in 1.12.
 */
process SPLIT_VCF_BY_CHR {
    tag "split-${meta.patient}"
    cpus 1
    memory "1 GB"
    container "dsbioinfo/bcftools:1.2"

    input:
        tuple val(meta), path(vcf)
        val(chrs)

    output:
        tuple val(meta), path("shards/${meta.patient}.*.shard.vcf")

    script:
    def keep = chrs.join(' ')
    """
    mkdir -p shards

    # Buffer the header, then append each record to its chromosome's shard, opening that shard with the
    # full header the first time the chromosome is seen. \$1 is CHROM.
    awk -v prefix="shards/${meta.patient}." -v keep="${keep}" '
        BEGIN { n = split(keep, a, " "); for (i = 1; i <= n; i++) ok[a[i]] = 1 }
        /^#/  { header = header \$0 "\\n"; next }
        !(\$1 in ok) { next }
        {
            out = prefix \$1 ".shard.vcf"
            if (!(out in started)) { printf "%s", header > out; started[out] = 1 }
            print >> out
        }
    ' ${vcf}

    # A VCF with no records on any wanted chromosome would emit no shard at all, and the patient would
    # silently leave the channel. Keep it present with a header-only shard, exactly as the old
    # per-chromosome `bcftools view` did for chromosomes it found nothing on.
    if [ -z "\$(ls -A shards)" ]; then
        first=\$(echo "${keep}" | awk '{print \$1}')
        grep '^#' ${vcf} > "shards/${meta.patient}.\${first}.shard.vcf" || true
    fi
    """
}
