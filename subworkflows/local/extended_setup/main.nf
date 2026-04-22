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


workflow EXTENDED_SETUP {

    take:
        basic_yaml_ch   // <- output of BASIC_SETUP

    main:

        /*
         * FAN-OUT: every module consumes SAME merged YAML
         */
        alphamissense_ch      = DOWNLOAD_ALPHAMISSENSE(basic_yaml_ch)
        ancestralallele_ch    = DOWNLOAD_ANCESTRALALLELE(basic_yaml_ch)
        cadd_ch               = DOWNLOAD_CADD(basic_yaml_ch)
        clinpred_ch           = DOWNLOAD_CLINPRED(basic_yaml_ch)
        dbnsfp_ch             = DOWNLOAD_DBNSFP(basic_yaml_ch)
        dbscsnv_ch            = DOWNLOAD_DBSCSNV(basic_yaml_ch)
        enformer_ch           = DOWNLOAD_ENFORMER(basic_yaml_ch)
        eve_ch                = DOWNLOAD_EVE(basic_yaml_ch)
        gwas_ch               = DOWNLOAD_GWAS(basic_yaml_ch)
        mavedb_ch             = DOWNLOAD_MAVEDB(basic_yaml_ch)
        maxentscan_ch         = DOWNLOAD_MAXENTSCAN(basic_yaml_ch)
        mutfunc_ch            = DOWNLOAD_MUTFUNC(basic_yaml_ch)
        phenotypeorthologous_ch = DOWNLOAD_PHENOTYPEORTHOLOGOUS(basic_yaml_ch)
        pli_ch                = DOWNLOAD_PLI(basic_yaml_ch)
        referencequality_ch   = DOWNLOAD_REFERENCEQUALITY(basic_yaml_ch)
        splicevault_ch        = DOWNLOAD_SPLICEVAULT(basic_yaml_ch)
        utrannotator_ch       = DOWNLOAD_UTRANNOTATOR(basic_yaml_ch)

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
            .map { dir, yaml -> yaml }
            .collect()

        merged_yaml = MERGE_EXTENDED_YAML(merged_input)

    emit:
        merged_yaml
}