#!/usr/bin/env python3
"""MuSA: per-patient variant review report.

Emits one self-contained HTML document per patient. No network dependency of any kind at read
time: no CDN, no webfont, no remote script. MuSA runs offline by default and these reports are
opened on lab desktops that may have no route out.

Why this file looks the way it does
-----------------------------------
The previous implementation rendered every variant as a <tr> and embedded a complete HTML detail
table inside a data-child attribute on each row. For a 68,338-variant exome that produced 683,381
DOM elements and a 167 MB file which took minutes to open, and it depended on jQuery, DataTables
and Google Fonts over the network.

This version embeds the same data as columnar, dictionary-encoded JSON (~26 MB for the same
patient) and renders through a virtual scroller, so the DOM holds a few hundred nodes regardless
of variant count. Design tokens live in musa_report_style.py, shared with the setup report.

Filtering contract
------------------
This script does not filter variants out of the document. It reads <patient>.filtered.maf (falling
back to <patient>.raw.maf when the filtered file is header-only) and embeds every row. The default
*view* is the review set, defined in review_flags() below; the full set is one click away and the
count of both is stated in the header.

Usage: build_annotate_report.py <patient_code> <use_vep_plugins> <offline> <skip_genebe> [logo]
"""

import base64
import datetime
import json
import os
import sys

import pandas as pd

import musa_report_style as style


# ── column configuration ──────────────────────────────────────────────────────
# Keys are original MAF column names. The report embeds every column listed here
# that exists in the MAF; anything absent is skipped with a warning rather than
# rendered as a blank field, so a missing column is visible as a missing column.

MAIN_COLUMNS = [
    ("Hugo_Symbol",    "Gene",        "gene"),
    ("genome_change",  "gDNA",        "mono"),
    ("HGVSc",          "cDNA",        "mono"),
    ("HGVSp_VEP",      "Protein",     "mono"),
    ("Consequence",    "Consequence", "consequence"),
    ("encoded_CLNSIG", "ClinVar",     "clinvar"),
    ("RENOVO_Class",   "ReNOVo",      "renovo"),
    ("MAX_AF",         "Max AF",      "af"),
]

DETAIL_COLUMNS = [
    ("Consequence",          "All consequences"),
    ("clinvar_id",           "ClinVar variation ID"),
    ("clinvar_OMIM_id",      "OMIM"),
    ("encoded_CLNREVSTAT",   "ClinVar review status"),
    ("clinvar_trait",        "ClinVar trait"),
    ("PUBMED",               "PubMed"),
    ("MAX_AF_POPS",          "Max AF population"),
    ("PL_score",             "ReNOVo pathogenicity score"),
    ("ref_context",          "Reference context"),
    ("bioinfo_params",       "Variant quality"),
    ("PhenotypeOrthologous_Mouse_phenotype", "Mouse orthologue phenotype"),
    ("PhenotypeOrthologous_Rat_phenotype",   "Rat orthologue phenotype"),
    # Present only when GeneBe ran (online mode).
    ("acmg_criteria",          "GeneBe ACMG criteria"),
    ("renovo_adj_acmg_score",  "GeneBe ACMG score"),
]


# ── arguments ─────────────────────────────────────────────────────────────────
def parse_args():
    args = sys.argv[1:]
    if len(args) < 4:
        sys.exit("Usage: build_annotate_report.py <patient_code> <use_vep_plugins> "
                 "<offline> <skip_genebe> [logo_path]")

    def _bool(v):
        return str(v).strip().upper() in ("TRUE", "1", "YES")

    return {
        "patient_code":    args[0],
        "use_vep_plugins": _bool(args[1]),
        "offline":         _bool(args[2]),
        "skip_genebe":     _bool(args[3]),
        "logo_path":       args[4] if len(args) > 4 else None,
    }


def load_logo_base64(logo_path):
    if not logo_path or not os.path.isfile(logo_path):
        if logo_path:
            print(f"  WARNING: logo not found at {logo_path}", file=sys.stderr)
        return None, None
    ext = os.path.splitext(logo_path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "svg": "image/svg+xml",
            "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
    with open(logo_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode(), mime


# ── MAF loading ───────────────────────────────────────────────────────────────
_HEADER_ONLY = object()


def _read_maf_file(path):
    if not os.path.isfile(path):
        return None
    try:
        df = pd.read_csv(path, sep="\t", low_memory=False, dtype=str)
        df = df.loc[:, ~df.columns.duplicated()]
        if df.empty:
            return _HEADER_ONLY
        print(f"  Loaded {len(df):,} rows x {len(df.columns)} cols from {path}", file=sys.stderr)
        return df
    except Exception as exc:
        print(f"  WARNING: could not read {path}: {exc}", file=sys.stderr)
        return None


def load_maf_data(patient_code):
    result = _read_maf_file(f"{patient_code}.filtered.maf")
    if result is _HEADER_ONLY or result is None:
        if result is _HEADER_ONLY:
            print("  Filtered MAF is header-only, falling back to raw MAF", file=sys.stderr)
        result = _read_maf_file(f"{patient_code}.raw.maf")
    if result is None or result is _HEADER_ONLY:
        raise RuntimeError(f"No usable MAF found for patient '{patient_code}'")
    return result


# ── review set ────────────────────────────────────────────────────────────────
def review_flags(df):
    """Return a list of 0/1 per row: is this variant in the default review view?

    Definition: rare (MAX_AF < 1%, absent counts as rare) AND (ClinVar-flagged as
    P/LP/VUS/conflicting OR protein-affecting consequence).

    Measured on four clinical exomes this yields 420-789 variants out of 65,000-73,000. The
    intent is the set a reviewer actually works through, not a claim that nothing else matters,
    which is why the full set stays in the document and one control away.
    """
    af = df["MAX_AF"] if "MAX_AF" in df.columns else pd.Series([""] * len(df))
    sig = df["encoded_CLNSIG"] if "encoded_CLNSIG" in df.columns else pd.Series([""] * len(df))
    csq = df["Consequence"] if "Consequence" in df.columns else pd.Series([""] * len(df))

    af_num = pd.to_numeric(af, errors="coerce")
    rare = af_num.isna() | (af_num < 0.01)

    flagged = sig.fillna("").map(lambda v: style.clinvar_chip(v)[0] in ("sig-p", "sig-lp", "sig-vus"))
    coding = csq.fillna("").map(style.is_protein_affecting)

    flags = (rare & (flagged | coding)).astype(int).tolist()
    print(f"  Review set: {sum(flags):,} of {len(flags):,} variants", file=sys.stderr)
    return flags


# ── payload ───────────────────────────────────────────────────────────────────
def build_payload(df, main_cols, detail_cols, flags, prio):
    """Columnar, per-column dictionary-encoded JSON.

    Row-oriented JSON for a 68k exome is 66 MB; this is 26 MB, and it stays plain JSON that any
    browser can parse and any text editor can grep. Compression was considered and rejected: it
    would need either DecompressionStream (too new for some institutional browsers) or a vendored
    decompressor, and the DOM node count was the real cost, not the bytes.
    """
    cols = [c for c, _, _ in main_cols] + [c for c, _ in detail_cols]
    data = {}
    for col in cols:
        values = df[col].fillna(".").astype(str).tolist() if col in df.columns else ["."] * len(df)
        uniq = sorted(set(values))
        if len(uniq) <= len(values) / 3:
            index = {v: i for i, v in enumerate(uniq)}
            data[col] = {"d": uniq, "i": [index[v] for v in values]}
        else:
            data[col] = {"v": values}
    return {
        "n": len(df),
        "main": [{"k": k, "label": lbl, "kind": kind} for k, lbl, kind in main_cols],
        "detail": [{"k": k, "label": lbl} for k, lbl in detail_cols],
        "data": data,
        "review": flags,
        "prio": prio,
    }


# Clinical priority ordering. The table sorts on this by default: a reviewer opening
# the report should land on the ClinVar pathogenic calls, not on alphabetical genes.
SIG_RANK = {"P": 6, "LP": 5, "CONF": 4, "VUS": 3, "LB": 2, "B": 1, "NC": 0}


def priority_scores(df):
    """Per-row sort key: ClinVar rank first, then a ReNOVo pathogenic call, then rarity.

    Encoded as one number so the JS sorts on a plain array:
        rank * 1000  +  renovo_pathogenic * 100  +  rarity_bonus
    """
    sig = df["encoded_CLNSIG"] if "encoded_CLNSIG" in df.columns else pd.Series([""] * len(df))
    rnv = df["RENOVO_Class"] if "RENOVO_Class" in df.columns else pd.Series([""] * len(df))
    af = pd.to_numeric(df["MAX_AF"], errors="coerce") if "MAX_AF" in df.columns else pd.Series([None] * len(df))

    out = []
    for s, r, a in zip(sig.fillna(""), rnv.fillna(""), af):
        rank = SIG_RANK.get(style.clinvar_chip(s)[1], 0)
        patho = 1 if style.renovo_chip(r)[1] == "PATH" else 0
        rare = 10 if (a != a or a is None) else (5 if a < 1e-4 else 0)   # a != a catches NaN
        out.append(rank * 1000 + patho * 100 + rare)
    return out


def overview(df, flags):
    """Everything the dashboard above the table needs, computed once in Python."""
    idx = [i for i, f in enumerate(flags) if f]
    sig = df["encoded_CLNSIG"].fillna("") if "encoded_CLNSIG" in df.columns else pd.Series([""] * len(df))
    rnv = df["RENOVO_Class"].fillna("") if "RENOVO_Class" in df.columns else pd.Series([""] * len(df))
    csq = df["Consequence"].fillna("") if "Consequence" in df.columns else pd.Series([""] * len(df))
    af = pd.to_numeric(df["MAX_AF"], errors="coerce") if "MAX_AF" in df.columns else pd.Series([None] * len(df))

    cv = [style.clinvar_chip(sig.iloc[i])[1] for i in idx]
    rn = [style.renovo_chip(rnv.iloc[i])[1] for i in idx]

    # Concordance between the two independent calls. This is the figure that is
    # specific to MuSA: nothing else in the report shows where its own classifier
    # and ClinVar disagree, or where it has an opinion and ClinVar has none.
    matrix = {}
    for c, r in zip(cv, rn):
        matrix[(c, r)] = matrix.get((c, r), 0) + 1

    novel = [i for i, c, r in zip(idx, cv, rn) if c == "NC" and r == "PATH"]
    contested = [i for i, c, r in zip(idx, cv, rn)
                 if (c in ("P", "LP") and r == "BEN") or (c in ("B", "LB") and r == "PATH")]
    flagged = [i for i, c in zip(idx, cv) if c in ("P", "LP", "CONF")]
    escalated = [i for i, c, r in zip(idx, cv, rn) if c == "VUS" and r == "PATH"]

    consequences = {}
    for i in idx:
        parts = style.split_consequences(csq.iloc[i])
        if parts:
            consequences[parts[0]] = consequences.get(parts[0], 0) + 1

    bands = {"not observed": 0, "under 0.01%": 0, "0.01% to 0.1%": 0, "0.1% to 1%": 0}
    for i in idx:
        a = af.iloc[i]
        if a != a or a is None:
            bands["not observed"] += 1
        elif a < 1e-4:
            bands["under 0.01%"] += 1
        elif a < 1e-3:
            bands["0.01% to 0.1%"] += 1
        else:
            bands["0.1% to 1%"] += 1

    return {
        "matrix": matrix,
        "novel": novel,
        "contested": contested,
        "flagged": flagged,
        "escalated": escalated,
        "consequences": sorted(consequences.items(), key=lambda kv: -kv[1]),
        "bands": bands,
        "n_review": len(idx),
    }


def summarise(df, flags):
    total = len(df)
    out = {"total": total, "review": sum(flags)}
    if "encoded_CLNSIG" in df.columns:
        classes = df["encoded_CLNSIG"].fillna("").map(lambda v: style.clinvar_chip(v)[1])
        counts = classes.value_counts().to_dict()
    else:
        counts = {}
    out["clinvar"] = {k: int(counts.get(k, 0)) for k in ("P", "LP", "VUS", "CONF", "LB", "B", "NC")}
    if "RENOVO_Class" in df.columns:
        rc = df["RENOVO_Class"].fillna("").map(lambda v: style.renovo_chip(v)[1])
        rcounts = rc.value_counts().to_dict()
    else:
        rcounts = {}
    out["renovo"] = {"PATH": int(rcounts.get("PATH", 0)), "BEN": int(rcounts.get("BEN", 0))}
    return out


# ── page CSS ──────────────────────────────────────────────────────────────────
PAGE_CSS = """
/* ── findings banner ──────────────────────────────────────────────────────── */
/* The first thing on the page is a sentence, not a number. A clinician opening a
   case wants the conclusion; the counts are the supporting detail underneath. */
.findings {
  padding: 1.5rem 1.5rem 1.25rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.findings-lede {
  font-family: var(--font-serif);
  font-size: var(--step-3); line-height: 1.35;
  max-width: 68ch; text-wrap: pretty;
}
.findings-lede b { font-weight: 700; font-variant-numeric: tabular-nums; }
.findings-lede .n-alert { color: var(--sig-p); }
.findings-lede .n-novel { color: var(--accent); }
.findings-sub {
  margin-top: 0.4rem; color: var(--ink-muted);
  font-size: var(--step-0); max-width: 68ch;
}

/* ── priority findings ────────────────────────────────────────────────────── */
.priority { display: grid; gap: 1.25rem 2rem; padding: 1.25rem 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(330px, 1fr));
  border-bottom: 1px solid var(--border); background: var(--surface); }
.priority-group h3 {
  font-size: var(--step-0); font-weight: 600; margin-bottom: 0.1rem;
}
.priority-why { font-size: var(--step--1); color: var(--ink-muted); margin-bottom: 0.5rem; }
.finding {
  display: grid; grid-template-columns: minmax(6ch, max-content) minmax(0, 1fr) auto auto;
  align-items: center; gap: 0.5rem; width: 100%;
  padding: 0.3rem 0.4rem; margin-left: -0.4rem;
  background: none; border: 0; border-radius: var(--radius);
  font: inherit; text-align: left; cursor: pointer;
}
.finding:hover { background: var(--surface-sunken); }
.finding-gene { font-weight: 700; white-space: nowrap; }
.finding-change {
  font-family: var(--font-mono); font-size: var(--step--1); color: var(--ink-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.priority-more { font-size: var(--step--1); color: var(--ink-muted); margin-top: 0.35rem; }
.priority-none { font-size: var(--step--1); color: var(--ink-muted); }

/* ── charts ───────────────────────────────────────────────────────────────── */
.charts {
  display: grid; gap: 1.5rem 2rem; padding: 1.25rem 1.5rem 1.5rem;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  border-bottom: 1px solid var(--border); background: var(--surface);
}
.chart h3 { font-size: var(--step-0); font-weight: 600; }
.chart-why { font-size: var(--step--1); color: var(--ink-muted); margin-bottom: 0.6rem; }
.chart-empty { font-size: var(--step--1); color: var(--ink-muted); }

.bar-row {
  display: grid; grid-template-columns: minmax(0,17ch) 1fr 5ch;
  align-items: center; gap: 0.6rem; padding: 0.13rem 0;
}
.bar-label {
  font-size: var(--step--1); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.bar-track { height: 9px; background: var(--surface-sunken); border-radius: 2px; }
.bar-fill { display: block; height: 100%; border-radius: 2px; }
.bar-fill.tone-accent { background: var(--accent); }
.bar-fill.tone-p      { background: var(--sig-p); }
.bar-fill.tone-lp     { background: var(--sig-lp); }
.bar-fill.tone-vus    { background: var(--sig-vus); }
.bar-fill.tone-nc     { background: var(--sig-nc); }
.bar-n {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step--1); text-align: right; color: var(--ink-muted);
}

table.matrix { border-collapse: collapse; font-size: var(--step--1); }
table.matrix th {
  font-weight: 600; color: var(--ink-muted); padding: 0.2rem 0.5rem;
  font-family: var(--font-mono);
}
table.matrix thead th { text-align: center; }
table.matrix tbody th { text-align: right; }
table.matrix td {
  width: 5.5ch; height: 26px; text-align: center;
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  border: 1px solid var(--surface);
  background: color-mix(in oklab, var(--accent) calc(var(--w, 0) * 100%), var(--surface-sunken));
}
table.matrix td.cell-disagree {
  background: color-mix(in oklab, var(--sig-p) calc(var(--w, 0) * 100%), var(--surface-sunken));
  outline: 1px solid var(--sig-p); outline-offset: -1px;
}
table.matrix td.cell-novel {
  background: color-mix(in oklab, var(--sig-lp) calc(var(--w, 0) * 100%), var(--surface-sunken));
}
.matrix-legend {
  display: flex; flex-wrap: wrap; gap: 0.75rem;
  margin-top: 0.5rem; font-size: var(--step--1); color: var(--ink-muted);
}
.matrix-legend span::before {
  content: ""; display: inline-block; width: 9px; height: 9px;
  margin-right: 0.3rem; border-radius: 2px; vertical-align: baseline;
}
.matrix-legend .k-novel::before    { background: var(--sig-lp); }
.matrix-legend .k-disagree::before { background: var(--sig-p); }

/* ── case summary ─────────────────────────────────────────────────────────── */
.summary {
  display: flex; flex-wrap: wrap; gap: 0 2.5rem;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.summary-block { display: flex; flex-direction: column; gap: 0.2rem; padding: 0.25rem 0; }
.summary-label {
  font-size: var(--step--1); color: var(--ink-muted);
}
.summary-value {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step-3); font-weight: 600; line-height: 1.1;
}
.summary-note { font-size: var(--step--1); color: var(--ink-muted); }
.summary-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; align-items: center; }

/* ── control bar ──────────────────────────────────────────────────────────── */
.controls {
  position: sticky; top: 0; z-index: var(--z-sticky);
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 0.75rem;
  padding: 0.6rem 1.5rem;
  background: var(--surface-sunken);
  border-bottom: 1px solid var(--border);
}
.controls-group { display: flex; align-items: center; gap: 0.35rem; }
.controls-sep { width: 1px; height: 20px; background: var(--border-strong); }
#search { min-width: 260px; }
.result-count {
  margin-left: auto;
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step--1); color: var(--ink-muted);
}

/* ── table + panel ────────────────────────────────────────────────────────── */
.workspace { display: flex; align-items: stretch; min-height: 0; }
.table-region { flex: 1 1 auto; min-width: 0; }
#scroller {
  height: 72vh; min-height: 340px;
  overflow: auto; background: var(--surface);
  border-right: 1px solid var(--border);
}
table.variants {
  width: 100%; border-collapse: separate; border-spacing: 0;
  font-size: var(--step-0);
}
table.variants thead th {
  position: sticky; top: 0; z-index: 2;
  background: var(--surface-sunken);
  text-align: left; font-weight: 600; font-size: var(--step--1);
  color: var(--ink-muted);
  padding: 0.45rem 0.6rem; white-space: nowrap;
  border-bottom: 1px solid var(--border-strong);
  cursor: pointer; user-select: none;
}
table.variants thead th:hover { color: var(--ink); }
table.variants thead th .sort-mark { opacity: 0.35; margin-left: 0.25rem; }
table.variants thead th[aria-sort="ascending"],
table.variants thead th[aria-sort="descending"] { color: var(--accent); }
table.variants thead th[aria-sort] .sort-mark { opacity: 1; }
#padTop td, #padBottom td { padding: 0; border: 0; }
table.variants tbody td {
  height: 30px; padding: 0 0.6rem; border-bottom: 1px solid var(--border);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 22ch;
}
table.variants tbody td.col-gene { font-weight: 600; max-width: 14ch; }
table.variants tbody td.col-mono,
table.variants tbody td.col-af { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
table.variants tbody tr { cursor: pointer; }
table.variants tbody tr:hover td { background: var(--surface-sunken); }
table.variants tbody tr[aria-selected="true"] td {
  background: var(--accent-weak);
  box-shadow: inset 0 0 0 1px var(--accent-ring);
}
.csq { font-size: var(--step--1); color: var(--ink-muted); }
table.variants tbody td.col-af { text-align: right; }
.af-value { color: var(--ink); }
.af-absent {
  font-family: var(--font-sans); font-style: italic;
  color: var(--sig-p); font-size: var(--step--1);
}
.stars { color: var(--sig-vus); letter-spacing: 0.06em; }
/* The hollow stars are aria-hidden decoration beside the spelled-out review status,
   but they still have to be legible: --border-strong sat at 1.74:1. */
.stars-empty { color: oklch(0.53 0.01 255); }
.stars-note { color: var(--ink-muted); font-family: var(--font-sans); }
.panel dd.plain { font-family: var(--font-sans); }

/* ── detail panel ─────────────────────────────────────────────────────────── */
.panel {
  flex: 0 0 380px; max-width: 380px;
  height: 72vh; min-height: 340px;
  overflow: auto; background: var(--surface); padding: 1rem 1.25rem;
}
.panel-empty { color: var(--ink-muted); font-size: var(--step-0); }
.panel-empty kbd {
  font-family: var(--font-mono); font-size: var(--step--1);
  padding: 0.05rem 0.3rem; border: 1px solid var(--border-strong);
  border-radius: 3px; background: var(--surface-sunken);
}
.panel h3 {
  font-family: var(--font-serif); font-size: var(--step-2); font-weight: 600;
  margin-bottom: 0.15rem;
}
.panel-gdna {
  font-family: var(--font-mono); font-size: var(--step--1);
  color: var(--ink-muted); word-break: break-all; margin-bottom: 0.75rem;
}
.panel-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 1rem; }
.panel dl { display: grid; grid-template-columns: minmax(0,1fr); gap: 0.6rem; }
.panel dt {
  font-size: var(--step--1); color: var(--ink-muted); margin-bottom: 0.1rem;
}
.panel dd {
  font-family: var(--font-mono); font-size: var(--step--1);
  word-break: break-word; white-space: pre-wrap;
}
.panel dd.absent { font-family: var(--font-sans); color: var(--ink-muted); font-style: italic; }
.panel-links { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 1rem; }
.panel-links a {
  font-size: var(--step--1); padding: 0.25rem 0.55rem;
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  text-decoration: none; color: var(--accent);
}
.panel-links a:hover { background: var(--accent-weak); }

@media (max-width: 1100px) {
  .workspace { flex-direction: column; }
  .panel { flex: 1 1 auto; max-width: none; height: auto; border-top: 1px solid var(--border); }
  #scroller { height: 60vh; border-right: none; }
}
"""


# ── page JS ───────────────────────────────────────────────────────────────────
PAGE_JS = r"""
(function () {
  "use strict";

  var P = window.__MUSA__;
  var ROW_H = 30;          // must match the CSS row height for the scroller maths
  var OVERSCAN = 8;

  // Dictionary-encoded columns are expanded lazily, once, on first access.
  var cache = {};
  function col(key) {
    if (cache[key]) return cache[key];
    var c = P.data[key];
    if (!c) { cache[key] = []; return cache[key]; }
    cache[key] = c.v ? c.v : c.i.map(function (i) { return c.d[i]; });
    return cache[key];
  }

  function absent(v) { return !v || v === "." || v === "nan" || v === "None"; }
  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  // ── renderers, mirroring musa_report_style.py so labels and colours agree ──
  function clinvarChip(v) {
    var s = (v || "").toLowerCase(), cls = "sig-nc", code = "NC", note = "not classified";
    if (absent(v)) { /* defaults */ }
    else if (s.indexOf("conflict") >= 0) { cls = "sig-vus"; code = "CONF"; note = "conflicting"; }
    else if (s.indexOf("likely") >= 0 && s.indexOf("patho") >= 0) { cls = "sig-lp"; code = "LP"; note = "likely pathogenic"; }
    else if (s.indexOf("likely") >= 0 && s.indexOf("benign") >= 0) { cls = "sig-lb"; code = "LB"; note = "likely benign"; }
    else if (s.indexOf("patho") >= 0) { cls = "sig-p"; code = "P"; note = "pathogenic"; }
    else if (s.indexOf("benign") >= 0) { cls = "sig-b"; code = "B"; note = "benign"; }
    else if (s.indexOf("vus") >= 0 || s.indexOf("uncertain") >= 0) { cls = "sig-vus"; code = "VUS"; note = "uncertain significance"; }
    return { cls: cls, code: code, note: note };
  }

  var CONF = { HP: "high", IP: "intermediate", LP: "low" };
  function renovoChip(v) {
    if (absent(v)) return { cls: "sig-nc", code: "--", note: "no ReNOVo call" };
    var parts = String(v).split(" ");
    if (parts.length !== 2 || !CONF[parts[0]]) return { cls: "sig-nc", code: v, note: v };
    var patho = parts[1].toLowerCase().indexOf("patho") === 0;
    return {
      cls: patho ? "sig-p" : "sig-b",
      code: patho ? "PATH" : "BEN",
      note: (patho ? "pathogenic" : "benign") + ", " + CONF[parts[0]] + " confidence"
    };
  }

  // Allele frequency reads as a figure, not a chip. In the review set every variant is
  // rare by construction, so chipping the column produced a solid wall of warm colour
  // that carried no information. Only absence from the population databases, which is
  // the genuinely notable case, gets emphasis.
  function afCell(v) {
    if (absent(v)) return '<span class="af-absent">not observed</span>';
    var f = parseFloat(v);
    if (isNaN(f)) return esc(v);
    var label = f < 1e-4 ? f.toExponential(1) : f.toPrecision(2);
    return '<span class="af-value">' + esc(label) + "</span>";
  }

  // Several consequences per variant: MuSA's MAF joins with ',', VEP's VCF with '&'.
  function firstConsequence(v) {
    if (absent(v)) return "—";
    return String(v).split(/[,&]/)[0].replace(/_/g, " ");
  }

  var STARS = {
    "0": "no assertion criteria provided",
    "1": "criteria provided, single submitter",
    "2": "criteria provided, multiple submitters, no conflicts",
    "3": "reviewed by expert panel",
    "4": "practice guideline"
  };
  // encoded_CLNREVSTAT is a 0-4 gold-star rating. A bare "2" tells a reader nothing.
  function starsHTML(v) {
    if (!STARS.hasOwnProperty(String(v).trim())) return null;
    var n = parseInt(v, 10);
    return '<span class="stars" aria-hidden="true">' +
           "★".repeat(n) + '<span class="stars-empty">' + "☆".repeat(4 - n) + "</span></span> " +
           '<span class="stars-note">' + esc(STARS[String(v).trim()]) + "</span>";
  }

  function chipHTML(c) {
    return '<span class="chip ' + c.cls + '"><b>' + esc(c.code) + '</b>' +
           '<span class="sr-only"> ' + esc(c.note) + '</span></span>';
  }

  // Franklin URLs are derived here rather than embedded: one URL per variant would
  // add a 68,000-entry unique column to the payload for data we can recompute.
  function franklinURL(gc) {
    if (absent(gc)) return "";
    var g = String(gc).replace(/^g\./, "");
    var m = /^chr([^:]+):/.exec(g);
    if (!m) return "";
    var chrom = m[1], snv = /:([0-9]+)([ACGT])>([ACGT])$/.exec(g);
    if (snv) return "https://franklin.genoox.com/clinical-db/variant/snp/chr" +
                    chrom + "-" + snv[1] + "-" + snv[2] + "-" + snv[3] + "-hg38";
    return "";
  }

  // ── state ────────────────────────────────────────────────────────────────
  var view = "review";
  var query = "";
  var sortKey = "__prio", sortDir = -1;   // ClinVar pathogenic first, on open
  var order = [];
  var selected = -1;

  var SEARCH_KEYS = ["Hugo_Symbol", "genome_change", "HGVSc", "HGVSp_VEP"];

  function rebuild() {
    var n = P.n, review = P.review, out = [];
    var q = query.trim().toLowerCase();
    var searchCols = q ? SEARCH_KEYS.map(col) : null;

    for (var i = 0; i < n; i++) {
      if (view === "review" && !review[i]) continue;
      if (q) {
        var hit = false;
        for (var c = 0; c < searchCols.length; c++) {
          var val = searchCols[c][i];
          if (val && val.toLowerCase().indexOf(q) >= 0) { hit = true; break; }
        }
        if (!hit) continue;
      }
      out.push(i);
    }

    if (sortKey) {
      var vals = sortKey === "__prio" ? P.prio : col(sortKey);
      var numeric = sortKey === "__prio" || sortKey === "MAX_AF" || sortKey === "PL_score";
      out.sort(function (a, b) {
        var x = vals[a], y = vals[b];
        if (numeric) {
          var fx = parseFloat(x), fy = parseFloat(y);
          if (isNaN(fx)) fx = -Infinity;
          if (isNaN(fy)) fy = -Infinity;
          return (fx - fy) * sortDir;
        }
        return String(x).localeCompare(String(y)) * sortDir;
      });
    }

    order = out;
    document.getElementById("resultCount").textContent =
      out.length.toLocaleString() + (out.length === 1 ? " variant" : " variants");
    scroller.scrollTop = 0;
    render();
  }

  // ── virtual rendering ────────────────────────────────────────────────────
  var scroller = document.getElementById("scroller");
  var tbody = document.getElementById("tbody");
  var padTop = document.getElementById("padTop");
  var padBottom = document.getElementById("padBottom");

  function render() {
    var total = order.length;
    var viewH = scroller.clientHeight;
    var first = Math.max(0, Math.floor(scroller.scrollTop / ROW_H) - OVERSCAN);
    var count = Math.min(total - first, Math.ceil(viewH / ROW_H) + OVERSCAN * 2);

    padTop.style.height = (first * ROW_H) + "px";
    padBottom.style.height = Math.max(0, (total - first - count) * ROW_H) + "px";

    var gene = col("Hugo_Symbol"), gdna = col("genome_change"), cdna = col("HGVSc"),
        prot = col("HGVSp_VEP"), csq = col("Consequence"),
        cvs = col("encoded_CLNSIG"), rnv = col("RENOVO_Class"), maf = col("MAX_AF");

    var html = [];
    for (var k = 0; k < count; k++) {
      var i = order[first + k];
      html.push(
        '<tr data-row="' + i + '" role="row" aria-selected="' + (i === selected) + '">' +
        '<td class="col-gene">' + esc(absent(gene[i]) ? "—" : gene[i]) + '</td>' +
        '<td class="col-mono">' + esc(absent(gdna[i]) ? "—" : gdna[i]) + '</td>' +
        '<td class="col-mono">' + esc(absent(cdna[i]) ? "—" : cdna[i]) + '</td>' +
        '<td class="col-mono">' + esc(absent(prot[i]) ? "—" : prot[i]) + '</td>' +
        '<td class="csq">' + esc(firstConsequence(csq[i])) + '</td>' +
        '<td>' + chipHTML(clinvarChip(cvs[i])) + '</td>' +
        '<td>' + chipHTML(renovoChip(rnv[i])) + '</td>' +
        '<td class="col-af">' + afCell(maf[i]) + '</td>' +
        '</tr>'
      );
    }
    tbody.innerHTML = html.join("");
  }

  // ── detail panel ─────────────────────────────────────────────────────────
  function select(i) {
    selected = i;
    var panel = document.getElementById("panel");
    if (i < 0) {
      panel.innerHTML = '<p class="panel-empty">Select a variant to see its full evidence.<br><br>' +
        'Use <kbd>&uarr;</kbd> and <kbd>&darr;</kbd> to walk the list without losing your place.</p>';
      return;
    }
    var gene = col("Hugo_Symbol")[i], gdna = col("genome_change")[i];
    var parts = [];
    parts.push('<h3>' + esc(absent(gene) ? "Unnamed gene" : gene) + '</h3>');
    parts.push('<p class="panel-gdna">' + esc(absent(gdna) ? "—" : gdna) + '</p>');
    parts.push('<div class="panel-chips">' +
      chipHTML(clinvarChip(col("encoded_CLNSIG")[i])) +
      chipHTML(renovoChip(col("RENOVO_Class")[i])) +
      '</div>');

    parts.push("<dl>");
    P.detail.forEach(function (d) {
      var v = col(d.k)[i];
      parts.push("<dt>" + esc(d.label) + "</dt>");
      if (absent(v)) { parts.push('<dd class="absent">not reported</dd>'); return; }
      if (d.k === "encoded_CLNREVSTAT") {
        var st = starsHTML(v);
        parts.push('<dd class="plain">' + (st || esc(v)) + "</dd>");
        return;
      }
      if (d.k.indexOf("PhenotypeOrthologous") === 0) {
        var seen = {}, items = [];
        String(v).split(",").forEach(function (t) {
          t = t.trim().replace(/^_+/, "").replace(/_/g, " ");
          if (t && !seen[t]) { seen[t] = 1; items.push(t); }
        });
        parts.push('<dd class="plain">' + esc(items.join(", ")) + "</dd>");
        return;
      }
      if (d.k === "Consequence") {
        parts.push('<dd class="plain">' + esc(String(v).split(/[,&]/).join(", ").replace(/_/g, " ")) + "</dd>");
        return;
      }
      parts.push("<dd>" + esc(v).replace(/,/g, ", ") + "</dd>");
    });
    parts.push("</dl>");

    var links = [];
    var fu = franklinURL(gdna);
    if (fu) links.push('<a href="' + fu + '" target="_blank" rel="noopener noreferrer">Open in Franklin</a>');
    var cvid = col("clinvar_id")[i];
    if (!absent(cvid)) {
      String(cvid).split(",").forEach(function (id) {
        id = id.trim();
        if (id) links.push('<a href="https://www.ncbi.nlm.nih.gov/clinvar/variation/' + encodeURIComponent(id) +
                           '" target="_blank" rel="noopener noreferrer">ClinVar ' + esc(id) + '</a>');
      });
    }
    var omim = col("clinvar_OMIM_id")[i];
    if (!absent(omim)) {
      String(omim).split(",").forEach(function (id) {
        id = id.trim();
        if (id) links.push('<a href="https://www.omim.org/entry/' + encodeURIComponent(id) +
                           '" target="_blank" rel="noopener noreferrer">OMIM ' + esc(id) + '</a>');
      });
    }
    var pm = col("PUBMED")[i];
    if (!absent(pm)) {
      String(pm).split(",").slice(0, 6).forEach(function (id) {
        id = id.trim();
        if (id) links.push('<a href="https://pubmed.ncbi.nlm.nih.gov/' + encodeURIComponent(id) +
                           '/" target="_blank" rel="noopener noreferrer">PMID ' + esc(id) + '</a>');
      });
    }
    if (links.length) parts.push('<div class="panel-links">' + links.join("") + "</div>");

    panel.innerHTML = parts.join("");
    render();
  }

  // ── events ───────────────────────────────────────────────────────────────
  scroller.addEventListener("scroll", render, { passive: true });
  window.addEventListener("resize", render);

  tbody.addEventListener("click", function (e) {
    var tr = e.target.closest("tr[data-row]");
    if (tr) select(parseInt(tr.dataset.row, 10));
  });

  Array.prototype.forEach.call(document.querySelectorAll("[data-goto]"), function (btn) {
    btn.addEventListener("click", function () {
      var i = parseInt(btn.dataset.goto, 10);
      if (view === "review" && !P.review[i]) {
        document.querySelector('[data-view="all"]').click();
      }
      var pos = order.indexOf(i);
      if (pos < 0) { query = ""; document.getElementById("search").value = ""; rebuild(); pos = order.indexOf(i); }
      if (pos < 0) return;
      scroller.scrollTop = Math.max(0, pos * ROW_H - scroller.clientHeight / 2);
      select(i);
      scroller.scrollIntoView({ block: "start" });
    });
  });

  document.getElementById("search").addEventListener("input", function (e) {
    query = e.target.value;
    rebuild();
  });

  Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (btn) {
    btn.addEventListener("click", function () {
      view = btn.dataset.view;
      Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      rebuild();
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll("th[data-key]"), function (th) {
    th.addEventListener("click", function () {
      var key = th.dataset.key;
      if (sortKey === key) sortDir = -sortDir;
      else { sortKey = key; sortDir = 1; }
      Array.prototype.forEach.call(document.querySelectorAll("th[data-key]"), function (t) {
        t.removeAttribute("aria-sort");
      });
      th.setAttribute("aria-sort", sortDir === 1 ? "ascending" : "descending");
      rebuild();
    });
    th.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); th.click(); }
    });
  });

  // Arrow keys walk the list with the panel pinned, which is the point of docking
  // it rather than expanding rows inline.
  document.addEventListener("keydown", function (e) {
    if (e.target.tagName === "INPUT") return;
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    var pos = order.indexOf(selected);
    if (pos < 0) pos = e.key === "ArrowDown" ? -1 : order.length;
    var next = pos + (e.key === "ArrowDown" ? 1 : -1);
    if (next < 0 || next >= order.length) return;
    select(order[next]);
    var top = next * ROW_H, bottom = top + ROW_H;
    if (top < scroller.scrollTop) scroller.scrollTop = top;
    else if (bottom > scroller.scrollTop + scroller.clientHeight)
      scroller.scrollTop = bottom - scroller.clientHeight;
  });

  select(-1);
  rebuild();
})();
"""


# ── page assembly ─────────────────────────────────────────────────────────────
PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>__PATIENT__ &middot; MuSA variant review</title>
<style>
__TOKENS__
__BASE_CSS__
__PAGE_CSS__
</style>
</head>
<body>

<header class="masthead">
  <div class="masthead-id">
    __LOGO__
    <span class="masthead-doc">Variant review</span>
  </div>
  <div class="masthead-meta">
    <span>Patient <b>__PATIENT__</b></span>
    <span>Assembly <b>hg38</b></span>
    <span>Generated <b>__GENERATED__</b></span>
    <span>Mode <b>__MODE__</b></span>
  </div>
</header>

<section class="summary">
  <div class="summary-block">
    <span class="summary-label">In review set</span>
    <span class="summary-value">__REVIEW__</span>
    <span class="summary-note">rare and either ClinVar-flagged or protein-affecting</span>
  </div>
  <div class="summary-block">
    <span class="summary-label">Annotated in total</span>
    <span class="summary-value">__TOTAL__</span>
    <span class="summary-note">every variant is in this document</span>
  </div>
  <div class="summary-block">
    <span class="summary-label">ClinVar</span>
    <span class="summary-chips">__CLINVAR_CHIPS__</span>
    <span class="summary-note">across all annotated variants</span>
  </div>
  <div class="summary-block">
    <span class="summary-label">ReNOVo</span>
    <span class="summary-chips">__RENOVO_CHIPS__</span>
    <span class="summary-note">MuSA's own pathogenicity call</span>
  </div>
</section>

<section class="findings">
  <p class="findings-lede">__LEDE__</p>
  <p class="findings-sub">__LEDE_SUB__</p>
</section>

<section class="priority" aria-label="Priority findings">__PRIORITY__</section>

<section class="charts" aria-label="Overview">
  <div class="chart">
    <h3>ClinVar against ReNOVo</h3>
    <p class="chart-why">Where the two independent calls agree, disagree, or where only MuSA has an
    opinion. Review-set variants only.</p>
    __MATRIX__
    <div class="matrix-legend">
      <span class="k-novel">ClinVar has no classification</span>
      <span class="k-disagree">calls contradict each other</span>
    </div>
  </div>
  <div class="chart">
    <h3>Consequence profile</h3>
    <p class="chart-why">What kind of change the review set is made of.</p>
    __CSQ_BARS__
  </div>
  <div class="chart">
    <h3>Population frequency</h3>
    <p class="chart-why">How rare the review set is. Absence from gnomAD is itself evidence.</p>
    __AF_BARS__
  </div>
</section>

<div class="controls no-print">
  <div class="controls-group" role="group" aria-label="Which variants to show">
    <button class="btn" type="button" data-view="review" aria-pressed="true">Review set</button>
    <button class="btn" type="button" data-view="all" aria-pressed="false">All variants</button>
  </div>
  <div class="controls-sep" aria-hidden="true"></div>
  <label class="sr-only" for="search">Search by gene, coordinate, cDNA or protein change</label>
  <input class="field" id="search" type="search" placeholder="Gene, coordinate, cDNA or protein change"/>
  <span class="result-count" id="resultCount" role="status" aria-live="polite"></span>
</div>

<div class="workspace">
  <div class="table-region">
    <div id="scroller">
      <table class="variants">
        <thead><tr>__HEADERS__</tr></thead>
        <tbody id="tbody-pad-top-holder">
          <tr id="padTop" aria-hidden="true"><td colspan="__NCOL__"></td></tr>
        </tbody>
        <tbody id="tbody"></tbody>
        <tbody>
          <tr id="padBottom" aria-hidden="true"><td colspan="__NCOL__"></td></tr>
        </tbody>
      </table>
    </div>
  </div>
  <aside class="panel" id="panel" aria-live="polite" aria-label="Variant detail"></aside>
</div>

<footer class="doc-footer">
  <span>MuSA &middot; multi-source variant annotation &middot; patient __PATIENT__</span>
  <span>__GENERATED__</span>
  <span>IRCCS Istituto Ortopedico Rizzoli, Bologna</span>
</footer>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
window.__MUSA__ = JSON.parse(document.getElementById("payload").textContent);
__PAGE_JS__
</script>
</body>
</html>
"""


def _bars(items, total, tone="accent", limit=8, scale=None):
    """Horizontal proportional bars. Plain HTML, no chart library, no SVG path data."""
    rows = []
    top = scale or max([n for _, n in items[:limit]] or [1])
    for label, n in items[:limit]:
        pct = n / top * 100
        rows.append(
            '<div class="bar-row">'
            f'<span class="bar-label">{html_escape(str(label).replace("_", " "))}</span>'
            f'<span class="bar-track"><span class="bar-fill tone-{tone}" style="width:{pct:.2f}%"></span></span>'
            f'<span class="bar-n">{n:,}</span>'
            "</div>"
        )
    return "".join(rows)


def html_escape(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _finding_rows(df, indices, limit=8):
    """Compact clickable rows for the priority findings list."""
    get = lambda col, i: (str(df[col].iloc[i]) if col in df.columns else ".")
    out = []
    for i in indices[:limit]:
        gene = get("Hugo_Symbol", i)
        prot = get("HGVSp_VEP", i)
        gdna = get("genome_change", i)
        cvc, cvcode, cvnote = style.clinvar_chip(get("encoded_CLNSIG", i))
        rnc, rncode, rnnote = style.renovo_chip(get("RENOVO_Class", i))
        change = prot if prot not in (".", "nan", "") else gdna
        out.append(
            f'<button class="finding" type="button" data-goto="{i}">'
            f'<span class="finding-gene">{html_escape(gene if gene != "." else "—")}</span>'
            f'<span class="finding-change">{html_escape(change)}</span>'
            f'<span class="chip {cvc}"><b>{cvcode}</b><span class="sr-only"> ClinVar {cvnote}</span></span>'
            f'<span class="chip {rnc}"><b>{rncode}</b><span class="sr-only"> ReNOVo {rnnote}</span></span>'
            "</button>"
        )
    return "".join(out)


def _matrix_html(matrix):
    """ClinVar (rows) against ReNOVo (columns), counts in cells.

    Off-diagonal cells are where the two independent calls disagree, which is the
    only place in the report that comparison is visible.
    """
    cv_order = [c for c in ("P", "LP", "CONF", "VUS", "LB", "B", "NC")
                if any(k[0] == c for k in matrix)]
    rn_order = [r for r in ("PATH", "BEN", "--") if any(k[1] == r for k in matrix)]
    if not cv_order or not rn_order:
        return '<p class="chart-empty">No paired calls to compare.</p>'
    peak = max(matrix.values()) or 1

    head = "".join(f'<th scope="col">{r}</th>' for r in rn_order)
    body = []
    for c in cv_order:
        cells = []
        for r in rn_order:
            n = matrix.get((c, r), 0)
            disagree = (c in ("P", "LP") and r == "BEN") or (c in ("B", "LB") and r == "PATH")
            novel = c == "NC" and r == "PATH"
            cls = "cell-disagree" if disagree and n else ("cell-novel" if novel and n else "")
            weight = 0 if not n else 0.12 + 0.68 * (n / peak)
            cells.append(
                f'<td class="{cls}" style="--w:{weight:.3f}">'
                f'<span class="cell-n">{n:,}</span></td>'
            )
        body.append(f'<tr><th scope="row">{c}</th>{"".join(cells)}</tr>')
    return (
        '<table class="matrix"><caption class="sr-only">ClinVar significance by ReNOVo call'
        f'</caption><thead><tr><td></td>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'
    )


def _chip(cls, code, note, count):
    return (f'<span class="chip {cls}"><b>{code}</b>'
            f'<span class="chip-note">{count:,}</span>'
            f'<span class="sr-only"> {note}</span></span>')


def build_html_page(patient_code, payload, stats, ov, df, logo_b64, logo_mime, mode):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # assets/MuSA_logo_light.png is the dark-ink wordmark, i.e. the one for a light
    # ground; when present it *is* the wordmark, so the text version would duplicate it.
    logo = (f'<img class="masthead-logo" src="data:{logo_mime};base64,{logo_b64}" alt="MuSA"/>'
            if logo_b64
            else '<span class="masthead-wordmark">MuSA</span>')

    cv = stats["clinvar"]
    clinvar_chips = "".join(
        _chip(cls, code, note, cv.get(code, 0))
        for code, cls, note in [
            ("P", "sig-p", "pathogenic"),
            ("LP", "sig-lp", "likely pathogenic"),
            ("VUS", "sig-vus", "uncertain significance"),
            ("CONF", "sig-vus", "conflicting interpretations"),
            ("LB", "sig-lb", "likely benign"),
            ("B", "sig-b", "benign"),
            ("NC", "sig-nc", "not classified"),
        ] if cv.get(code, 0)
    ) or '<span class="summary-note">no ClinVar annotation present</span>'

    rn = stats["renovo"]
    renovo_chips = "".join(
        _chip(cls, code, note, rn.get(code, 0))
        for code, cls, note in [
            ("PATH", "sig-p", "ReNOVo pathogenic"),
            ("BEN", "sig-b", "ReNOVo benign"),
        ] if rn.get(code, 0)
    ) or '<span class="summary-note">no ReNOVo call present</span>'

    n_flag, n_esc, n_novel = len(ov["flagged"]), len(ov["escalated"]), len(ov["novel"])
    n_contested, n_unobs = len(ov["contested"]), ov["bands"]["not observed"]

    clauses = []
    if n_flag:
        clauses.append(f'<b class="n-alert">{n_flag}</b> '
                       f'{"variant carries" if n_flag == 1 else "variants carry"} a ClinVar '
                       f'pathogenic, likely-pathogenic or conflicting classification')
    if n_novel:
        clauses.append(f'ReNOVo calls <b class="n-novel">{n_novel}</b> '
                       f'{"variant" if n_novel == 1 else "variants"} pathogenic that ClinVar '
                       f'has never classified')
    if n_esc:
        clauses.append(f'<b>{n_esc}</b> ClinVar {"VUS is" if n_esc == 1 else "VUS are"} '
                       f'called pathogenic by ReNOVo')
    if not clauses:
        lede = (f'No ClinVar pathogenic call and no ReNOVo pathogenic call in the '
                f'<b>{ov["n_review"]:,}</b>-variant review set.')
    else:
        lede = (clauses[0][0].upper() + clauses[0][1:] + ". "
                + ". ".join(c[0].upper() + c[1:] for c in clauses[1:])
                + ("." if len(clauses) > 1 else ""))

    lede_sub = (f'Counted across the {ov["n_review"]:,}-variant review set, drawn from '
                f'{stats["total"]:,} annotated. {n_unobs:,} of the review set are absent from '
                f'gnomAD entirely.')
    if n_contested:
        lede_sub += (f' {n_contested} '
                     f'{"call is" if n_contested == 1 else "calls are"} contradicted between '
                     f'ClinVar and ReNOVo and should be read carefully.')

    # ── priority findings, grouped by why they are here ──────────────────────
    groups = []
    for key, title, why in [
        ("flagged", "ClinVar flagged", "pathogenic, likely pathogenic or conflicting"),
        ("escalated", "ClinVar VUS, ReNOVo pathogenic", "uncertain to ClinVar, called by MuSA"),
        ("novel", "Not classified by ClinVar", "ReNOVo calls these pathogenic"),
        ("contested", "Calls contradict", "the two classifiers disagree outright"),
    ]:
        items = ov[key]
        if not items:
            continue
        more = (f'<p class="priority-more">and {len(items) - 8:,} more, sorted to the top of '
                f'the table</p>' if len(items) > 8 else "")
        groups.append(
            f'<div class="priority-group"><h3>{title} <span class="bar-n">{len(items):,}</span></h3>'
            f'<p class="priority-why">{why}</p>{_finding_rows(df, items)}{more}</div>'
        )
    priority_html = "".join(groups) or (
        '<p class="priority-none">Nothing in the review set is flagged by ClinVar or called '
        'pathogenic by ReNOVo.</p>')

    # Rarity is the point of this chart, so each band carries its own tone rather than
    # one colour scaled by count, which made the *commonest* band the loudest bar.
    af_tones = {"not observed": "p", "under 0.01%": "lp",
                "0.01% to 0.1%": "vus", "0.1% to 1%": "nc"}
    af_bars = "".join(
        _bars([(k, v)], ov["n_review"], tone=af_tones[k], scale=max(ov["bands"].values()) or 1)
        for k, v in ov["bands"].items() if v
    )

    headers = "".join(
        f'<th scope="col" tabindex="0" data-key="{c["k"]}">{c["label"]}'
        f'<span class="sort-mark" aria-hidden="true">&#8597;</span></th>'
        for c in payload["main"]
    )

    return (PAGE_HTML
            .replace("__TOKENS__", style.TOKENS)
            .replace("__BASE_CSS__", style.BASE_CSS)
            .replace("__PAGE_CSS__", PAGE_CSS)
            .replace("__PAGE_JS__", PAGE_JS)
            .replace("__LEDE__", lede)
            .replace("__LEDE_SUB__", lede_sub)
            .replace("__PRIORITY__", priority_html)
            .replace("__MATRIX__", _matrix_html(ov["matrix"]))
            .replace("__CSQ_BARS__", _bars(ov["consequences"], ov["n_review"]))
            .replace("__AF_BARS__", af_bars)
            .replace("__NCOL__", str(len(payload["main"])))
            .replace("__HEADERS__", headers)
            .replace("__CLINVAR_CHIPS__", clinvar_chips)
            .replace("__RENOVO_CHIPS__", renovo_chips)
            .replace("__REVIEW__", f"{stats['review']:,}")
            .replace("__TOTAL__", f"{stats['total']:,}")
            .replace("__GENERATED__", now)
            .replace("__MODE__", mode)
            .replace("__LOGO__", logo)
            .replace("__PATIENT__", patient_code.upper())
            .replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":"))))


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    params = parse_args()
    patient = params["patient_code"]
    offline = params["offline"] or params["skip_genebe"]

    print("MuSA: annotation report", file=sys.stderr)
    print(f"  patient        : {patient}", file=sys.stderr)
    print(f"  offline        : {offline}", file=sys.stderr)
    print(f"  use_vep_plugins: {params['use_vep_plugins']}", file=sys.stderr)

    logo_b64, logo_mime = load_logo_base64(params["logo_path"])
    df = load_maf_data(patient)

    main_cols = [c for c in MAIN_COLUMNS if c[0] in df.columns]
    detail_cols = [c for c in DETAIL_COLUMNS if c[0] in df.columns]

    missing = [c[0] for c in MAIN_COLUMNS + DETAIL_COLUMNS if c[0] not in df.columns]
    if missing:
        print(f"  Columns absent from MAF, omitted from the report: {', '.join(missing)}",
              file=sys.stderr)

    flags = review_flags(df)
    prio = priority_scores(df)
    payload = build_payload(df, main_cols, detail_cols, flags, prio)
    stats = summarise(df, flags)
    ov = overview(df, flags)
    print(f"  Priority: {len(ov['flagged'])} ClinVar-flagged, {len(ov['escalated'])} escalated "
          f"VUS, {len(ov['novel'])} ReNOVo-only, {len(ov['contested'])} contested",
          file=sys.stderr)

    html = build_html_page(
        patient_code=patient,
        payload=payload,
        stats=stats,
        ov=ov,
        df=df,
        logo_b64=logo_b64,
        logo_mime=logo_mime,
        mode="offline" if offline else "online",
    )

    out_file = f"{patient}_maf_dashboard.html"
    with open(out_file, "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"OK  Report written: {out_file} ({os.path.getsize(out_file) / 1e6:.1f} MB)",
          file=sys.stderr)

    # lib/ directory expected by the Nextflow output tuple
    os.makedirs("lib", exist_ok=True)
    open("lib/.keep", "w").close()


if __name__ == "__main__":
    main()
