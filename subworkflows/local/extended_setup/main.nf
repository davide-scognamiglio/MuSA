include { MERGE_YAML as MERGE_EXTENDED_YAML } from '../../../modules/local/merge_yaml'

include { DOWNLOAD_ALPHAMISSENSE } from '../../../modules/local/download_alphamissense'
include { DOWNLOAD_ANCESTRALALLELE } from '../../../modules/local/download_ancestralallele'
include { DOWNLOAD_CADD } from '../../../modules/local/download_cadd'
include { DOWNLOAD_CLINPRED } from '../../../modules/local/download_clinpred'
include { DOWNLOAD_DBNSFP } from '../../../modules/local/download_dbnsfp'
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
include { REFRESH_DBNSFP_ALIGNED_COLUMNS } from '../refresh_dbnsfp_aligned_columns'


workflow EXTENDED_SETUP {

    take:
        basic_yaml_ch      // <- output of BASIC_SETUP
        changed_entries_ch // <- output of BASIC_SETUP (NO_FILE sentinel unless --update_db_only)

    main:

        /*
         * FAN-OUT: every module consumes SAME merged YAML + changed-entries gate
         */
        alphamissense_ch      = DOWNLOAD_ALPHAMISSENSE(basic_yaml_ch, changed_entries_ch)
        ancestralallele_ch    = DOWNLOAD_ANCESTRALALLELE(basic_yaml_ch, changed_entries_ch)
        cadd_ch               = DOWNLOAD_CADD(basic_yaml_ch, changed_entries_ch)
        clinpred_ch           = DOWNLOAD_CLINPRED(basic_yaml_ch, changed_entries_ch)
        dbnsfp_ch             = DOWNLOAD_DBNSFP(basic_yaml_ch, changed_entries_ch)
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

        /*
         * FAN-IN: merge all updated YAMLs
         */
        merged_input =
            alphamissense_ch
            .mix(ancestralallele_ch,
                cadd_ch,
                clinpred_ch,
                dbnsfp_ch,
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
                utrannotator_ch)
            .collect()

        merged_yaml = MERGE_EXTENDED_YAML(merged_input)

        // BASIC_SETUP already ran this off its own dbnsfp_ch/refgen_ch; wired here too so a run of
        // extended_setup alone (dbNSFP re-downloaded here on line 37) still produces the file. The
        // two calls cannot race or duplicate work: extended_setup structurally runs after
        // basic_setup completes (it takes basic_yaml_ch as an input), so by the time this fires the
        // file basic_setup's own call wrote (if any) is already on disk, and the existence gate in
        // REFRESH_DBNSFP_ALIGNED_COLUMNS skips accordingly. basic_yaml_ch doubles as the
        // "reference genome is ready" token: MERGE_BASIC_YAML only emits after every basic_setup
        // download — refgenome included — has completed.
        REFRESH_DBNSFP_ALIGNED_COLUMNS(dbnsfp_ch, basic_yaml_ch)

    emit:
        merged_yaml
}
