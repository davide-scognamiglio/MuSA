#!/usr/bin/env python3
"""Collapse dbNSFP's per-transcript arrays to the MANE Select transcript.

dbNSFP reports transcript-specific fields as ';'-delimited arrays positionally aligned with
Ensembl_transcriptid:

    Ensembl_transcriptid   ENST...884306;ENST...325103;ENST...361490;ENST...699131
    MANE_dbNSFP            .;.;Select;.
    SIFT_score             .;0.169;0.169;.

Which element belongs to the clinically canonical isoform is encoded in MANE_dbNSFP and nowhere else:
the offset of "Select" is the offset to read in every other array. Ensembl_transcriptid runs in
parallel and names the transcript at each position, but it does not mark which position is MANE. So a
consumer reading `SIFT_score` alone cannot tell which number to trust. This rewrites every
transcript-aligned column to the single element at the MANE position, leaving gene-level and
variant-level columns untouched.

WHICH COLUMNS ARE TRANSCRIPT-ALIGNED COMES FROM A FIXED LIST, not from inspecting the file at hand:
<dbNSFP install>/dbnsfp_transcript_aligned_columns.txt (path is the caller's job — MERGE_ANNOTATIONS
passes it explicitly), rebuilt automatically after every dbNSFP download/update
(subworkflows/local/refresh_dbnsfp_aligned_columns, against a small committed probe panel — there is
no patient MAF yet at that point) and regeneratable by hand for an audit against real MAFs with
bin/gen_dbnsfp_aligned_columns.py. Deriving it per run instead would let the same column collapse for
one patient and stay an array for the next, purely because that patient's file happened to hold no
multi-transcript row for it.

Getting that list wrong is not symmetric. A column missing from it stays a ';' array: awkward, never
false. A column wrongly ON it would attach one transcript's score to a different transcript, in
silence. dbNSFP also uses ';' for gene-level fields — GO_*, Pathway(*), HPO_*, MIM_*, Orphanet_*,
GenCC_* — whose element count has nothing to do with transcripts, so those must never appear there.
As a second line of defence, a value is rewritten only when its element count matches the transcript
count on that row.

When a variant has no MANE transcript the position falls back, in order, to MANE Plus Clinical, then
to the transcript VEP itself picked, then to the first element. One index is chosen per row and used
for every column, so the columns can never disagree with each other. MANE_dbNSFP is collapsed with
the rest, which makes it the provenance flag: a '.' there means the scores on that row did not come
from a MANE transcript.

Usage:
    dbnsfp_collapse_mane.py <dbnsfp.tsv> <out.tsv> <aligned_columns.txt> [vep.tsv]

The TSVs are the key-prefixed, sorted files produced by MERGE_ANNOTATIONS (column 1 is 0_KEY).
The VEP file is optional and only supplies the fallback transcript (its `Feature` column).
"""

from __future__ import annotations

import sys
from collections import Counter

TID_COL = "Ensembl_transcriptid"
# MERGE_ANNOTATIONS renames dbNSFP's MANE to clear the name clash with VEP's single-value MANE, so
# the asset lists it under its dbNSFP name while the file being read here already uses the new one.
MANE_COL = "MANE_dbNSFP"
MANE_SRC_COL = "MANE"


def _read_vep_features(path: str) -> dict[str, str]:
    """key -> the transcript VEP picked, used only as a fallback position."""
    features: dict[str, str] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        try:
            fi = header.index("Feature")
        except ValueError:
            return features
        for line in fh:
            row = line.rstrip("\n").split("\t")
            if len(row) > fi:
                features[row[0]] = row[fi]
    return features


def _load_aligned(path: str, header: list[str]) -> tuple[set[int], int]:
    """Indices of the header columns named in the allowlist. Returns (indices, names_listed)."""
    names: set[str] = set()
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if line:
                names.add(line.split("\t")[0].strip())
    listed = len(names)
    # The MANE array is transcript-aligned by definition - it is the thing the offset is read from -
    # and the asset carries it under dbNSFP's own name, from before the rename.
    if MANE_SRC_COL in names:
        names.add(MANE_COL)
    names.add(MANE_COL)

    # A name can appear twice in a dbNSFP header: the search program emits the variant table and the
    # gene table side by side, and Uniprot_acc exists in both. The two are unrelated - one tracks
    # transcripts, one is gene-level - and an allowlist keyed by name cannot tell them apart, so
    # collapsing "the" column would scramble the gene-level twin. Skip every duplicated name; leaving
    # an array intact costs nothing, misindexing it is silent corruption.
    seen: Counter[str] = Counter(header)
    ambiguous = {c for c in names if seen[c] > 1}
    if ambiguous:
        sys.stderr.write(
            f"[collapse_mane] skipping {len(ambiguous)} listed column(s) that appear more than once "
            f"in the header: {', '.join(sorted(ambiguous))}\n"
        )

    return {i for i, c in enumerate(header) if c in names and c not in ambiguous}, listed


def _pick_index(tids: list[str], manes: list[str], feature: str | None) -> tuple[int, str]:
    """The one position every column on this row is collapsed to, plus why."""
    for i, v in enumerate(manes):
        if "select" in v.lower():
            return i, "MANE Select"
    for i, v in enumerate(manes):
        if "plus" in v.lower():
            return i, "MANE Plus Clinical"
    if feature:
        want = feature.split(".")[0]
        for i, t in enumerate(tids):
            if t.split(".")[0] == want:
                return i, "VEP-picked transcript"
    return 0, "first transcript"


def main() -> int:
    if len(sys.argv) not in (4, 5):
        sys.exit(f"usage: {sys.argv[0]} <dbnsfp.tsv> <out.tsv> <aligned_columns.txt> [vep.tsv]")
    src, dest, cols_file = sys.argv[1], sys.argv[2], sys.argv[3]
    features = _read_vep_features(sys.argv[4]) if len(sys.argv) == 5 else {}

    with open(src, encoding="utf-8", errors="replace") as fh:
        header_line = fh.readline()
    header = header_line.rstrip("\n").split("\t")

    # An empty shard, or a dbNSFP build without the transcript list: nothing to align against.
    if TID_COL not in header or MANE_COL not in header:
        missing = ", ".join(c for c in (TID_COL, MANE_COL) if c not in header)
        sys.stderr.write(
            f"[collapse_mane] {missing} absent - copying through, arrays left as they are\n"
        )
        with open(src, encoding="utf-8", errors="replace") as fin, open(
            dest, "w", encoding="utf-8"
        ) as fout:
            for line in fin:
                fout.write(line)
        return 0

    tid_i, mane_i = header.index(TID_COL), header.index(MANE_COL)
    aligned, listed = _load_aligned(cols_file, header)
    sys.stderr.write(
        f"[collapse_mane] {len(aligned)} of {listed} listed columns present in this file "
        f"({len(header)} columns total)\n"
    )

    reasons: Counter[str] = Counter()
    with open(src, encoding="utf-8", errors="replace") as fin, open(
        dest, "w", encoding="utf-8"
    ) as fout:
        fin.readline()  # header is written from header_line, not passed through the loop
        fout.write(header_line)
        for line in fin:
            row = line.rstrip("\n").split("\t")
            if len(row) <= tid_i:
                fout.write(line)
                continue
            tids = row[tid_i].split(";")
            if len(tids) < 2:
                fout.write(line)  # already one value per column
                continue

            manes = row[mane_i].split(";") if mane_i < len(row) else []
            idx, why = _pick_index(tids, manes, features.get(row[0]))
            reasons[why] += 1

            for i in aligned:
                if i >= len(row):
                    continue
                parts = row[i].split(";")
                # Defensive: the file-wide rule should make this hold on every row.
                if len(parts) == len(tids):
                    row[i] = parts[idx]
            fout.write("\t".join(row) + "\n")

    total = sum(reasons.values())
    sys.stderr.write(f"[collapse_mane] collapsed {total} multi-transcript rows\n")
    for why, n in reasons.most_common():
        sys.stderr.write(f"[collapse_mane]   {n:>8} via {why}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
