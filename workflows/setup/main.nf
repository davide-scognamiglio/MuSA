/*
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    CONFIG FILES
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
*/

params.date = new java.util.Date().format('yyMMdd')

include { BASIC_SETUP    } from '../../subworkflows/local/basic_setup'
include { EXTENDED_SETUP } from '../../subworkflows/local/extended_setup'
include { BUILD_SETUP_REPORT } from '../../modules/local/build_setup_report'

workflow SETUP {

    main:
        // Always run basic setup, emits a merged yaml
        BASIC_SETUP()
        basic_yaml = BASIC_SETUP.out.merged_yaml

        if (params.download_vep_plugins == true) {
            // Extended setup takes the basic merged yaml as input
            EXTENDED_SETUP(basic_yaml)
            report_input = EXTENDED_SETUP.out.merged_yaml
        } else {
            report_input = basic_yaml
        }

        final_ch = BUILD_SETUP_REPORT(report_input)
}