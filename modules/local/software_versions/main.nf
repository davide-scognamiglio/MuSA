/*
 * MuSA
 * Module: SOFTWARE_VERSIONS
 * Purpose: Record the version of each tool this run uses, from the image the run uses it in
 *
 * Every MuSA process names a fixed container image, so asking each image once per run records
 * exactly what annotated the patients, without every module carrying a versions.yml output (which
 * would turn each module into a multi-output process and break the stage chains). The result is
 * <outdir>/pipeline_info/software_versions.yml and the report's Annotation sources view; database
 * versions are recorded separately, in the same view and in <data_dir>/dbs_manifest.yaml.
 */

process SOFTWARE_VERSIONS {
    tag "${tool}"
    container "${image}"

    input:
        tuple val(tool), val(image)

    output:
        path("${tool}.version.yml")

    script:
    """
    set -euo pipefail
    case "${tool}" in
        ensembl-vep)    v=\$(vep --help | awk '/^ *ensembl-vep +:/ {print \$3}') ;;
        bcftools)       v=\$(bcftools --version | head -1 | cut -d' ' -f2) ;;
        gatk)           v=\$(gatk --version 2>/dev/null | sed -n 's/.*(GATK) v//p') ;;
        vcf2maf)        v="vcf2maf.pl md5 \$(md5sum /opt/vcf2maf.pl | cut -c1-12), perl \$(perl -e 'print substr(\$^V, 1)')" ;;
        musa-helper)    v="python \$(python3 -c 'import platform; print(platform.python_version())'), pandas \$(python3 -c 'import pandas; print(pandas.__version__)'), R \$(Rscript -e 'cat(format(getRversion()))'), java \$(java -version 2>&1 | head -1 | cut -d'"' -f2)" ;;
        musa-report)    v="python \$(python3 -c 'import platform; print(platform.python_version())'), pandas \$(python3 -c 'import pandas; print(pandas.__version__)')" ;;
        renovo-rebuild) v=\$(renovo-rebuild --version | awk '{print \$2}') ;;
        genebe)         v=\$(genebe version | awk '{print \$NF}') ;;
        *)              echo "SOFTWARE_VERSIONS: no version command for ${tool}" >&2; exit 1 ;;
    esac
    printf '%s:\\n  image: "%s"\\n  version: "%s"\\n' "${tool}" "${image}" "\$v" > ${tool}.version.yml
    """
}
