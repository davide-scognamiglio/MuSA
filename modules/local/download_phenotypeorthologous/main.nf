/*
 * MuSA
 * Module: DOWNLOAD_PHENOTYPEORTHOLOGOUS
 * Purpose: Download vep plugin database
 */


process DOWNLOAD_PHENOTYPEORTHOLOGOUS {
    tag "vep_setup"
    publishDir "${params.data_dir}/vep_data", mode: 'copy', overwrite: true, pattern: "PhenotypeOrthologous"
    container "dsbioinfo/musa-helper:rebuild"

    input:
        file manifest

    output:
        tuple path("PhenotypeOrthologous"),file('phenotypeorthologous_manifest.yaml')

 script:
    """
    set -euo pipefail

    source manifest_parser.sh
    source download_and_hash.sh

    parse_manifest "${manifest}"

    mkdir -p PhenotypeOrthologous
    cd PhenotypeOrthologous

    prefix="vep_phenotypeorthologous"

    # ---------------------------------------
    # 2-file bundle: main + index
    # vcf entry has no infix:  vep_phenotypeorthologous_url
    # tbi entry has infix:     vep_phenotypeorthologous_tbi_url
    # ---------------------------------------
    for suffix in "" "tbi"; do

        if [ -z "\$suffix" ]; then
            var_prefix="\${prefix}"
            label="vcf"
        else
            var_prefix="\${prefix}_\${suffix}"
            label="\$suffix"
        fi

        url_var="\${var_prefix}_url"
        method_var="\${var_prefix}_method"
        out_var="\${var_prefix}_out"

        echo "[INFO] Processing \${prefix} - \${label} (looking up \$url_var)"

        if [ -z "\${!url_var+x}" ]; then
            echo "[ERROR] Variable '\$url_var' is not set. Check your manifest." >&2
            exit 1
        fi

        sha=\$(download_and_compute_sha "\${!url_var}" "\${!method_var}" "\${!out_var}")

        write_computed_sha256 "../${manifest}" "\${var_prefix}" "\$sha"

        echo "[INFO] \${var_prefix} hash written"
    
    done

    cd ..

    mv ${manifest} phenotypeorthologous_manifest.yaml
    """
}