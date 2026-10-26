/*
 * MuSA
 * Module: GROUP_GENOTYPES
 * Purpose: For a family or cohort annotated from one joint-called VCF: every member's genotype
 *          (GT_/DP_/GQ_/AD_/VAF_<sample>, or the <group>.genotypes.tsv.gz sidecar above
 *          --max_member_columns members), then the family facts (Inheritance, segregation,
 *          compound heterozygosity) or the cohort counts. See bin/group_genotypes.py.
 */

process GROUP_GENOTYPES {
    tag "${meta.patient} | ${meta.mode}, ${meta.members.size()} members"
    container "dsbioinfo/musa-helper:rebuild"
    publishDir path: { "${params.outdir}/${params.date}/${meta.patient}" }, mode: "copy", pattern: "*.genotypes.tsv.gz"
    memory { 4.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        tuple val(meta), path(maf)

    output:
        tuple val(meta), path("${meta.patient}.group.maf"), emit: maf
        tuple val(meta), path("${meta.patient}.genotypes.tsv.gz"), emit: sidecar, optional: true

    script:
        def members = meta.members.collect { m -> [m.sample, m.role, m.sex, m.affected, m.family].join('\t') }.join('\n')
        def wide = meta.members.size() <= params.max_member_columns
        """
        cat > members.tsv <<'MEMBERS'
${members}
MEMBERS
        group_genotypes.py \\
            --maf ${maf} \\
            --members members.tsv \\
            --mode ${meta.mode} \\
            --max-member-columns ${params.max_member_columns} \\
            ${wide ? '' : "--sidecar ${meta.patient}.genotypes.tsv.gz"} \\
            --dn-min-dp ${params.dn_min_dp} \\
            --dn-min-gq ${params.dn_min_gq} \\
            --dn-max-parent-alt ${params.dn_max_parent_alt} \\
            --output ${meta.patient}.group.maf
        """
}
