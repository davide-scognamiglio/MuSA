/*
 * MuSA
 * Module: ARGUS_SETUP
 * Purpose: Build ARGUS's data resources (ClinVar amino-acid index, PM1 residue density, PS4
 *          submitter counts, HPO term-gene table, REVEL rankscore map) from what MuSA setup
 *          installed, into <data_dir>/argus
 *
 * Runs at the end of every setup, both modes, once the downloads are installed. The sources are
 * resolved from this setup's merged manifest (the installed <data_dir>/dbs_manifest.yaml is only
 * written afterwards, by BUILD_SETUP_REPORT, and may name last setup's files) and passed to ARGUS
 * explicitly; a source that is absent (SpliceAI and dbNSFP on a basic setup, ClinVar's raw tables
 * on a data dir set up before MuSA kept them) is left out, ARGUS skips what needs it, and the
 * warnings reach the setup report. The previous <data_dir>/argus seeds the build, so ARGUS rebuilds
 * only resources whose sources or ARGUS version changed (0.4 s when nothing did).
 */

process ARGUS_SETUP {
    tag "argus_setup"
    container params.argus_container
    cpus params.n_core
    memory { 4.GB * task.attempt }
    errorStrategy 'retry'
    maxRetries 1

    input:
        path manifest

    output:
        path 'argus_notes.txt'

    script:
    """
    set -euo pipefail
    source manifest_parser.sh
    source download_and_hash.sh
    parse_manifest "${manifest}"

    # Seed with the installed resources so that unchanged ones are not rebuilt.
    if [[ -d /data/argus ]]; then cp -r /data/argus argus; else mkdir argus; fi

    args=()
    : > absent.txt
    add() {  # add <flag> <path> <what>: only when it is installed, else note it for the report
        if [[ -e "\$2" ]]; then args+=("\$1" "\$2"); else echo "\$3 not installed (\$2)" >> absent.txt; fi
    }
    add --variant-summary    "/data/clinvar_residues/\${clinvar_variant_summary_out:-none}" \
        "ClinVar variant_summary (set up before MuSA kept ClinVar's raw tables? remove clinvar_residues/ and rerun setup)"
    add --submission-summary "/data/clinvar_submissions/\${clinvar_submission_summary_out:-none}" \
        "ClinVar submission_summary (set up before MuSA kept ClinVar's raw tables? remove clinvar_submissions/ and rerun setup)"
    add --hpo-obo            "/data/hpo/\${hpo_out:-none}" "HPO ontology"
    add --hpo-g2p            "/data/hpo/\${hpo_genes_to_phenotype_out:-none}" "HPO genes_to_phenotype"
    add --spliceai-snv       "/data/vep_data/SpliceAI/\${vep_spliceai_snv_out:-none}" "SpliceAI (extended mode)"
    if compgen -G "/data/dbNSFP/dbNSFP/dbNSFP*_variant.chr*.gz" > /dev/null; then
        args+=(--dbnsfp-dir /data/dbNSFP/dbNSFP)
    else
        echo "dbNSFP (extended mode) not installed (/data/dbNSFP/dbNSFP)" >> absent.txt
    fi

    ARGUS setup --out argus --threads ${task.cpus} "\${args[@]}" 2> argus_setup.log \
        || { cat argus_setup.log >&2; exit 1; }
    cat argus_setup.log >&2

    install_into_data "argus" "/data/argus"

    # Setup report notices: which ARGUS built what, and every warning it logged.
    python3 - <<'PY' > argus_notes.txt
import json, re
m = json.load(open("/data/argus/argus_resources.json"))
built = ", ".join(sorted(m.get("resources", {}))) or "none"
print(f"ARGUS {m.get('argus_version', '?')} resources ({m.get('built', '?')}): {built}.")
for line in open("absent.txt"):
    print("ARGUS source " + line.strip() + ".")
seen = set()
for line in open("argus_setup.log"):
    if "[WARNING]" in line:
        msg = re.sub(r"^.*?\\[WARNING\\]\\s*(ARGUS[\\w.]*:\\s*)?", "", line.strip())
        if msg not in seen:
            seen.add(msg)
            print("ARGUS: " + msg)
PY
    cat argus_notes.txt
    """
}
