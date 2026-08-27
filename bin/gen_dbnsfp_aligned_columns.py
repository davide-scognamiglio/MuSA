#!/usr/bin/env python3
"""Regenerate the list of dbNSFP columns that are positionally aligned with the transcript list.

This produces `dbnsfp_transcript_aligned_columns.txt`, the fixed allowlist that
dbnsfp_collapse_mane.py reads at run time. It is deliberately not derived per pipeline run: that
would let the same column be collapsed for one patient and left alone for another, depending on
whether that patient's file happened to contain a multi-transcript row for it.

Two ways this runs, both producing the same file shape:

  AUTOMATIC   subworkflows/local/refresh_dbnsfp_aligned_columns runs this after every dbNSFP
              download/update, against the committed probe panel (assets/dbnsfp_probe_variants.vcf)
              annotated fresh through dbNSFP — there is no patient MAF yet at that point in the
              pipeline. Output lands inside the dbNSFP install itself
              (<data_dir>/dbNSFP/dbNSFP/dbnsfp_transcript_aligned_columns.txt), which is what makes
              it visible to every container without a projectDir bind mount (data_dir is already
              mounted). This is what MERGE_ANNOTATIONS actually reads at run time.

  MANUAL      Run this by hand against real patient MAFs to audit the automatic result, or if the
              probe panel ever needs to grow (e.g. a future dbNSFP release drops one of its six
              positions — see the probe VCF's own header for why six, and why those six). A manual
              run's output is not consumed by anything unless you copy it over the automatic one;
              treat it as a check, not a replacement.

The list is built from two sources, because neither is sufficient on its own:

  README    dbNSFP's own readme is authoritative about MEANING - which reference list a column's
            ';'-separated entries correspond to. Only Ensembl_transcriptid / Ensembl_proteinid are
            usable here (they are parallel lists, so the MANE offset indexes both). It is, however,
            incomplete: roughly 46 columns that the search program emits as per-transcript arrays
            (AlphaMissense, MetaRNN, DEOGEN2, ESM1b, LIST-S2, MisFit, MutPred2, MutationTaster,
            MutationAssessor, PHACTboost, VARITY, popEVE, ...) carry no such sentence at all.

  DATA      the actual output of dbNSFP's search program, which is what MuSA consumes. It differs
            from the readme in visible ways: SIFT4G is documented as comma-separated but arrives
            semicolon-separated, and Polyphen2 is documented as corresponding to Uniprot_acc yet
            tracks the transcript list in every observed row (Uniprot_acc itself has a different
            length in 7924 of 7928). The search program normalises separators and re-aligns arrays,
            so the shipped files are the operative truth for this pipeline.

A column qualifies from DATA only if its element count equals the transcript count in EVERY
multi-transcript row of EVERY sampled file; one mismatch anywhere disqualifies it. Sampling several
independent files is what keeps a coincidence from slipping through - Gene_other_names, for one,
happens to match the transcript count in about 6% of rows.

Counting is keyed by column NAME, which also handles a quirk of the search program's output: it emits
the variant table and the gene table side by side, so `Uniprot_acc` appears twice - once
transcript-aligned, once gene-level. The gene-level twin mismatches, that disqualifies the name, and
the column is left out altogether. That is the outcome we want: an allowlist of names cannot address
one of two same-named columns, and leaving an array intact is free while misindexing it is not.

Whatever the two sources say, anything listed in the readme's "Columns of dbNSFP_gene" section is
removed at the end. Those are gene-level fields (GO_*, Pathway(*), HPO_*, MIM_*, Orphanet_*, GenCC_*)
that also use ';' but have nothing to do with transcripts; indexing them by a transcript position
would silently scramble them. That exclusion is taken from the readme on purpose - it is exactly the
kind of question the readme answers definitively.

Usage:
    gen_dbnsfp_aligned_columns.py <readme.txt> <out.txt> <dbnsfp.tsv> [more.tsv ...]
"""

from __future__ import annotations

import re
import sys
from datetime import date

# "Multiple scores separated by ";", corresponding to Ensembl_proteinid."
# The reference must sit next to the separator clause: Uniprot_acc's own entry mentions
# "matching the Ensembl_proteinid" in its title line while its separator sentence names no list at
# all, and that column is NOT transcript-indexed.
ALIGNED_RE = re.compile(
    r'separated by "(?:.)"[,\s]*(?:corresponding to|corresponds to|matching)'
    r"\s+(?:the\s+)?Ensembl_(?:transcriptids?|proteinid)",
    re.I,
)
ENTRY_RE = re.compile(r"^(\d+)\t([^:]+):")
TID_COL = "Ensembl_transcriptid"


def _sections(readme: str) -> dict[str, dict[str, str]]:
    """Column name -> description, per 'Columns of <x>:' section of the readme."""
    lines = open(readme, encoding="utf-8", errors="replace").read().split("\n")
    bounds = [i for i, l in enumerate(lines) if l.startswith("Columns of ")]
    bounds.append(len(lines))

    out: dict[str, dict[str, str]] = {}
    for si, start in enumerate(bounds[:-1]):
        title = lines[start].strip().rstrip(":").replace("Columns of ", "")
        cols: dict[str, str] = {}
        name, buf = None, []
        for line in lines[start + 1 : bounds[si + 1]]:
            m = ENTRY_RE.match(line)
            if m:
                if name:
                    cols[name] = " ".join(buf)
                name, buf = m.group(2).strip(), [line]
            elif name:
                buf.append(line.strip())
        if name:
            cols[name] = " ".join(buf)
        out[title] = cols
    return out


def _from_data(paths: list[str]) -> tuple[set[str], dict[str, int]]:
    """Columns whose arrays track the transcript list in every multi-transcript row of every file."""
    hits: dict[str, int] = {}
    misses: set[str] = set()
    rows_seen = 0

    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as fh:
            header = fh.readline().rstrip("\n").split("\t")
            if TID_COL not in header:
                sys.stderr.write(f"  ! {path}: no {TID_COL}, skipped\n")
                continue
            tid = header.index(TID_COL)
            for line in fh:
                row = line.rstrip("\n").split("\t")
                if len(row) <= tid:
                    continue
                n = row[tid].count(";") + 1
                if n < 2:
                    continue
                rows_seen += 1
                for i, val in enumerate(row):
                    if ";" not in val or i >= len(header):
                        continue
                    col = header[i]
                    if val.count(";") + 1 == n:
                        hits[col] = hits.get(col, 0) + 1
                    else:
                        misses.add(col)

    return {c for c in hits if c not in misses}, {"rows": rows_seen}


def main() -> int:
    if len(sys.argv) < 4:
        sys.exit(f"usage: {sys.argv[0]} <readme.txt> <out.txt> <dbnsfp.tsv> [more.tsv ...]")
    readme, dest, samples = sys.argv[1], sys.argv[2], sys.argv[3:]

    sections = _sections(readme)
    variant = sections.get("dbNSFP_variant", {})
    gene = set(sections.get("dbNSFP_gene", {}))
    if not variant:
        sys.exit(f"{readme}: no 'Columns of dbNSFP_variant' section found")

    from_readme = {c for c, d in variant.items() if ALIGNED_RE.search(d)}
    from_readme.add(TID_COL)  # the reference list itself
    from_data, stats = _from_data(samples)

    keep = sorted((from_readme | from_data) - gene)
    dropped = sorted((from_readme | from_data) & gene)

    version = "unknown"
    with open(readme, encoding="utf-8", errors="replace") as fh:
        first = fh.readline().strip()
        if first:
            version = first

    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(
            "# dbNSFP columns positionally aligned with Ensembl_transcriptid.\n"
            "#\n"
            "# Read by bin/dbnsfp_collapse_mane.py: each of these is rewritten to the single element\n"
            "# at the MANE_dbNSFP offset when --dbnsfp_transcript_scores=mane. Every other column is\n"
            "# left untouched, so a name missing here is a column that stays a ';' array - annoying,\n"
            "# but never wrong. A name that does NOT belong here would silently attach one\n"
            "# transcript's score to another, so add entries only with evidence.\n"
            "#\n"
            "# GENERATED - do not hand-edit. Rebuilt automatically after every dbNSFP download/update\n"
            "# (subworkflows/local/refresh_dbnsfp_aligned_columns). Regenerate by hand only to audit\n"
            "# against real patient MAFs:\n"
            "#   bin/gen_dbnsfp_aligned_columns.py <readme.txt> \\\n"
            "#       dbnsfp_transcript_aligned_columns.txt <a.dbnsfp.tsv> <b.dbnsfp.tsv> ...\n"
            "#\n"
            f"# source readme : {version}\n"
            f"# generated     : {date.today().isoformat()}\n"
            f"# sampled files : {len(samples)} ({stats['rows']} multi-transcript rows)\n"
            f"# from readme   : {len(from_readme)}\n"
            f"# from data     : {len(from_data)}\n"
            f"# excluded as gene-level (readme 'Columns of dbNSFP_gene'): {len(dropped)}"
            f"{' - ' + ', '.join(dropped) if dropped else ''}\n"
            f"# total kept    : {len(keep)}\n"
            "#\n"
        )
        for col in keep:
            src = "readme+data" if col in from_readme and col in from_data else (
                "readme" if col in from_readme else "data"
            )
            fh.write(f"{col}\t# {src}\n")

    sys.stderr.write(
        f"[gen_aligned] readme={len(from_readme)} data={len(from_data)} "
        f"gene-excluded={len(dropped)} -> {len(keep)} columns written to {dest}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
