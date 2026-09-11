/*
 * MuSA
 * Subworkflow: REFRESH_DBNSFP_ALIGNED_COLUMNS
 * Purpose: After a dbNSFP download/update, (re)build dbnsfp_transcript_aligned_columns.txt
 *
 * Reuses the same split -> per-chromosome dbNSFP query -> gather chain a real sample goes through
 * (SPLIT_VCF_BY_CHR / DBNSFP_ANNOTATE_VCF_CHR / GATHER_DBNSFP_TSV, unmodified), fed with the
 * committed probe panel instead of a patient VCF, then hands the result to
 * GEN_DBNSFP_ALIGNED_COLUMNS.
 *
 * Gated on the OUTPUT file, not on whether DOWNLOAD_DBNSFP actually downloaded anything: the module
 * skips its own download when the manifest is unchanged, but that skip is decided inside its bash
 * script and never surfaces as a Nextflow value, so there is nothing upstream to branch on directly.
 * Checking file(...).exists() from a `.filter{}` on the channel instead of a plain top-level `if`
 * is what makes this correct rather than coincidental: a `.filter{}` closure runs when the upstream
 * value actually arrives, i.e. after DOWNLOAD_DBNSFP has genuinely completed for this run, so it
 * sees the real post-download state - not a stale snapshot taken before this run started. A fresh
 * download replaces the whole dbNSFP folder (DOWNLOAD_DBNSFP's `mv $extracted_dir dbNSFP`), so the
 * aligned-columns file from any previous version is gone with it and this reliably regenerates; an
 * unchanged/skipped download leaves the existing file in place and this reliably no-ops, without
 * ever paying for the (cheap, but not free) java dbNSFP query.
 *
 * Takes `refgenome_ready` as a second completion token, not just `dbnsfp_ready`: BASIC_SETUP and
 * EXTENDED_SETUP run DOWNLOAD_DBNSFP and DOWNLOAD_REFGENOME in parallel, and chrom_list() reads the
 * reference .fai off disk with a plain (eager) Groovy file read. Called directly at workflow-script
 * level, that read would race DOWNLOAD_REFGENOME on a first-ever setup run, when the .fai does not
 * exist yet. Routing it through `.map{}` on refgenome_ready defers the read until that upstream
 * value has actually arrived, the same trick `gated` below uses for the aligned-columns file.
 */

include { SPLIT_VCF_BY_CHR } from '../../../modules/local/split_vcf_by_chr'
include { DBNSFP_ANNOTATE_VCF_CHR } from '../../../modules/local/dbnsfp_annotate_vcf_chr'
include { GATHER_DBNSFP_TSV } from '../../../modules/local/gather_dbnsfp_tsv'
include { GEN_DBNSFP_ALIGNED_COLUMNS } from '../../../modules/local/gen_dbnsfp_aligned_columns'
include { chrom_list } from '../../../lib/annot_utils.nf'

workflow REFRESH_DBNSFP_ALIGNED_COLUMNS {

    take:
        dbnsfp_ready     // DOWNLOAD_DBNSFP's manifest output — value only matters as a completion token
        refgenome_ready  // DOWNLOAD_REFGENOME's output — same, needed before chrom_list() can read the .fai

    main:

        aligned_cols_path = "${params.data_dir}/dbNSFP/dbNSFP/dbnsfp_transcript_aligned_columns.txt"

        gated = dbnsfp_ready.filter { !file(aligned_cols_path).exists() }

        probe_ch = gated.map {
            tuple([patient: 'dbnsfp_probe'], file("${projectDir}/assets/dbnsfp_probe_variants.vcf"))
        }

        // Same shard -> annotate -> gather composition as ANNOTATE_GERMLINE's dbNSFP branch
        // (subworkflows/local/annotate_germline/main.nf) — kept in lock-step deliberately, so a
        // future change to that chain's shape is a change here too, not a silent divergence.
        chr_ch = refgenome_ready.map {
            chrom_list("${params.data_dir}/vep_data/reference_genome/${params.build}.fa.fai")
        }

        shards = SPLIT_VCF_BY_CHR(probe_ch, chr_ch)
            .transpose()
            .map { meta, shard ->
                def m = (shard.name =~ /\.([^.]+)\.shard\.vcf$/)
                if (!m) error "SPLIT_VCF_BY_CHR produced an unparseable shard name: ${shard.name}"
                tuple(meta, m[0][1], shard)
            }
        shard_tsv = DBNSFP_ANNOTATE_VCF_CHR(shards)

        probe_tsv = GATHER_DBNSFP_TSV(
            shard_tsv
                .map { meta, chr, tsv -> tuple(meta, tsv) }
                .groupTuple()
        )

        GEN_DBNSFP_ALIGNED_COLUMNS(probe_tsv.map { meta, tsv -> tsv })
}
