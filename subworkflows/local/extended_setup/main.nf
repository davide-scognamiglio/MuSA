include { MERGE_YAML as MERGE_EXTENDED_YAML } from '../../../modules/local/merge_yaml'
include { DOWNLOAD_DBNSFP } from '../../../modules/local/download_dbnsfp'
include { REFRESH_DBNSFP_ALIGNED_COLUMNS } from '../refresh_dbnsfp_aligned_columns'

include { DOWNLOAD_ALPHAMISSENSE } from '../../../modules/local/download_alphamissense'
include { DOWNLOAD_ANCESTRALALLELE } from '../../../modules/local/download_ancestralallele'
include { DOWNLOAD_CADD } from '../../../modules/local/download_cadd'
include { DOWNLOAD_DBSCSNV } from '../../../modules/local/download_dbscsnv'
include { DOWNLOAD_ENFORMER } from '../../../modules/local/download_enformer'
include { DOWNLOAD_EVE } from '../../../modules/local/download_eve'
include { DOWNLOAD_GWAS } from '../../../modules/local/download_gwas'
include { DOWNLOAD_MAVEDB } from '../../../modules/local/download_mavedb'
include { DOWNLOAD_MAXENTSCAN } from '../../../modules/local/download_maxentscan'
include { DOWNLOAD_MUTFUNC } from '../../../modules/local/download_mutfunc'
include { DOWNLOAD_PHENOTYPEORTHOLOGOUS } from '../../../modules/local/download_phenotypeorthologous'
include { DOWNLOAD_PLI } from '../../../modules/local/download_pli'
include { DOWNLOAD_REFERENCEQUALITY } from '../../../modules/local/download_referencequality'
include { DOWNLOAD_SPLICEVAULT } from '../../../modules/local/download_splicevault'
include { DOWNLOAD_UTRANNOTATOR } from '../../../modules/local/download_utrannotator'
include { DOWNLOAD_SPLICEAI } from '../../../modules/local/download_spliceai'
include { DOWNLOAD_PROTVAR } from '../../../modules/local/download_protvar'
include { DOWNLOAD_INTACT } from '../../../modules/local/download_intact'
include { DOWNLOAD_G2P } from '../../../modules/local/download_g2p'
include { DOWNLOAD_RIBOSEQORFS } from '../../../modules/local/download_riboseqorfs'
include { DOWNLOAD_MECHPREDICT } from '../../../modules/local/download_mechpredict'
include { DOWNLOAD_DOSAGESENSITIVITY } from '../../../modules/local/download_dosagesensitivity'
include { DOWNLOAD_FLAGLRG } from '../../../modules/local/download_flaglrg'
include { DOWNLOAD_GENE_GFF3 } from '../../../modules/local/download_gene_gff3'


workflow EXTENDED_SETUP {

    take:
        basic_yaml_ch      // <- output of BASIC_SETUP
        changed_entries_ch // <- output of BASIC_SETUP (NO_FILE sentinel unless --update_db_only)

    main:

        /*
         * FAN-OUT: every module consumes SAME merged YAML + changed-entries gate.
         * dbNSFP is extended mode since 1.3: it needs a registration, and its ~47 GB serve
         * extended annotation only (its predictors, its gene file and RENOVO 1.5, which reads its
         * scores). It comes from the user (see checkDbnsfpSource in main.nf): a zip on disk, else
         * a URL. ClinPred is not here: dbNSFP carries the same scores (99.97% identical on NA12878), so its VEP
         * plugin (5.7 GB) added a score for 0.4% of variants. AlphaMissense stays: its plugin fills
         * the ~6% of missense variants whose MANE transcript has no AlphaMissense value in dbNSFP
         * (CLEAN_COLUMNS merges the two).
         */
        dbnsfp_zip = params.dbnsfp_zip ? file(params.dbnsfp_zip, checkIfExists: true) : file("${projectDir}/assets/NO_FILE")
        dbnsfp_ch  = DOWNLOAD_DBNSFP(basic_yaml_ch, changed_entries_ch, dbnsfp_zip, params.dbnsfp_url ?: "")

        // Rebuild dbnsfp_transcript_aligned_columns.txt when dbNSFP changed (or was never built for
        // the current install); no-ops otherwise, see the subworkflow's doc comment. basic_yaml_ch
        // doubles as the "reference genome installed" token: BASIC_SETUP emits it only after
        // DOWNLOAD_REFGENOME has finished.
        REFRESH_DBNSFP_ALIGNED_COLUMNS(dbnsfp_ch, basic_yaml_ch)

        alphamissense_ch      = DOWNLOAD_ALPHAMISSENSE(basic_yaml_ch, changed_entries_ch)
        ancestralallele_ch    = DOWNLOAD_ANCESTRALALLELE(basic_yaml_ch, changed_entries_ch)
        cadd_ch               = DOWNLOAD_CADD(basic_yaml_ch, changed_entries_ch)
        dbscsnv_ch            = DOWNLOAD_DBSCSNV(basic_yaml_ch, changed_entries_ch)
        enformer_ch           = DOWNLOAD_ENFORMER(basic_yaml_ch, changed_entries_ch)
        eve_ch                = DOWNLOAD_EVE(basic_yaml_ch, changed_entries_ch)
        gwas_ch               = DOWNLOAD_GWAS(basic_yaml_ch, changed_entries_ch)
        mavedb_ch             = DOWNLOAD_MAVEDB(basic_yaml_ch, changed_entries_ch)
        maxentscan_ch         = DOWNLOAD_MAXENTSCAN(basic_yaml_ch, changed_entries_ch)
        mutfunc_ch            = DOWNLOAD_MUTFUNC(basic_yaml_ch, changed_entries_ch)
        phenotypeorthologous_ch = DOWNLOAD_PHENOTYPEORTHOLOGOUS(basic_yaml_ch, changed_entries_ch)
        pli_ch                = DOWNLOAD_PLI(basic_yaml_ch, changed_entries_ch)
        referencequality_ch   = DOWNLOAD_REFERENCEQUALITY(basic_yaml_ch, changed_entries_ch)
        splicevault_ch        = DOWNLOAD_SPLICEVAULT(basic_yaml_ch, changed_entries_ch)
        utrannotator_ch       = DOWNLOAD_UTRANNOTATOR(basic_yaml_ch, changed_entries_ch)

        // Added in 1.4 (SpliceAI ... gene GFF3): see each module's header for what it brings.
        spliceai_ch           = DOWNLOAD_SPLICEAI(basic_yaml_ch, changed_entries_ch)
        protvar_ch            = DOWNLOAD_PROTVAR(basic_yaml_ch, changed_entries_ch)
        intact_ch             = DOWNLOAD_INTACT(basic_yaml_ch, changed_entries_ch)
        g2p_ch                = DOWNLOAD_G2P(basic_yaml_ch, changed_entries_ch)
        riboseqorfs_ch        = DOWNLOAD_RIBOSEQORFS(basic_yaml_ch, changed_entries_ch)
        mechpredict_ch        = DOWNLOAD_MECHPREDICT(basic_yaml_ch, changed_entries_ch)
        dosagesensitivity_ch  = DOWNLOAD_DOSAGESENSITIVITY(basic_yaml_ch, changed_entries_ch)
        flaglrg_ch            = DOWNLOAD_FLAGLRG(basic_yaml_ch, changed_entries_ch)
        gene_gff3_ch          = DOWNLOAD_GENE_GFF3(basic_yaml_ch, changed_entries_ch)

        /*
         * FAN-IN: merge all updated YAMLs
         */
        merged_input =
            dbnsfp_ch
            .mix(alphamissense_ch,
                ancestralallele_ch,
                cadd_ch,
                dbscsnv_ch,
                enformer_ch,
                eve_ch,
                gwas_ch,
                mavedb_ch,
                maxentscan_ch,
                mutfunc_ch,
                phenotypeorthologous_ch,
                pli_ch,
                referencequality_ch,
                splicevault_ch,
                utrannotator_ch,
                spliceai_ch,
                protvar_ch,
                intact_ch,
                g2p_ch,
                riboseqorfs_ch,
                mechpredict_ch,
                dosagesensitivity_ch,
                flaglrg_ch,
                gene_gff3_ch)
            .collect()

        merged_yaml = MERGE_EXTENDED_YAML(merged_input)

    emit:
        merged_yaml
}
