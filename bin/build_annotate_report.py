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
import re
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
    # The first three are also table columns, but the detail view now opens on its own
    # from the findings list, so it has to stand alone: a dialog that names the gene and
    # the genomic coordinate and then omits the protein change and the frequency is not
    # a variant record. Costs nothing in payload size, the columns are already embedded.
    ("HGVSc",                "cDNA"),
    ("HGVSp_VEP",            "Protein"),
    ("MAX_AF",               "Max allele frequency"),
    ("Consequence",          "All consequences"),
    ("CLNDN",                "ClinVar disease"),
    ("clinvar_id",           "ClinVar variation ID"),
    ("clinvar_OMIM_id",      "OMIM"),
    ("encoded_CLNREVSTAT",   "ClinVar review status"),
    ("ClinGen_GeneDisease_Disease",        "ClinGen gene-disease"),
    ("ClinGen_GeneDisease_MOI",            "Inheritance (ClinGen)"),
    ("ClinGen_GeneDisease_Classification", "Gene-disease validity"),
    ("gnomAD_pLI",           "gnomAD pLI"),
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


# ── ClinVar disease names ─────────────────────────────────────────────────────
# CLNDN is the field that answers "pathogenic for *what*". It arrives with spaces
# replaced by underscores and terms joined by commas, while the terms themselves
# contain commas ("Encephalopathy,_acute,_infection-induced,_susceptibility_to,_4").
# A separator comma is therefore one *not* followed by an underscore.

_DISEASE_NOISE = {
    "not provided", "not specified", "not_provided", "not_specified",
    "inborn genetic diseases", "see cases", "none provided",
    "human phenotype ontology", "association", "other",
}
# Terms that name a disease rather than a symptom or an umbrella label. Used only to
# choose which of several ClinVar terms to show first; nothing is discarded.
_DISEASE_HINT = re.compile(
    r"deficien|syndrome|disease|disorder|dystroph|anemi|anaemi|carcinom|cancer|"
    r"neoplas|tumor|tumour|myopath|neuropath|atroph|dysplas|malformation", re.I)


def disease_terms(value):
    """CLNDN to a de-duplicated list of readable disease names, best-first."""
    if not value or str(value) in (".", "nan", "None"):
        return []
    terms, seen = [], set()
    for raw in re.split(r",(?!_)", str(value)):
        term = raw.replace("_", " ").strip().strip(",").strip()
        key = term.lower()
        if not term or key in _DISEASE_NOISE or key in seen:
            continue
        if key.startswith("abnormality of"):      # generic HPO parent terms
            continue
        seen.add(key)
        terms.append(term)
    # A named disease beats a presenting sign ("Rhabdomyolysis" is true of the CPT2
    # variant, but "carnitine palmitoyltransferase II deficiency" is what it *is*).
    # Within that preference the shortest term is the least qualified one.
    named = [t for t in terms if _DISEASE_HINT.search(t)]
    if named:
        best = min(named, key=len)
        terms = [best] + [t for t in terms if t != best]
    return terms


def disease_label(value, limit=90):
    terms = disease_terms(value)
    if not terms:
        return ""
    label = terms[0]
    if len(label) > limit:
        label = label[:limit - 1].rstrip() + "…"
    if len(terms) > 1:
        label += f"  +{len(terms) - 1} more"
    return label


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


# The four reasons a variant is worth a second look, in the order a reviewer wants
# them. One definition drives three things: the blocks on the overview, the filter
# the table opens under when a block is clicked, and the label of that filter.
GROUPS = [
    ("flagged",   "ClinVar flagged",
     "pathogenic, likely pathogenic or conflicting in ClinVar"),
    ("escalated", "ClinVar VUS, ReNOVo pathogenic",
     "uncertain to ClinVar, called pathogenic by MuSA"),
    ("novel",     "Not classified by ClinVar",
     "ReNOVo calls these pathogenic and ClinVar has never seen them"),
    ("contested", "Calls contradict",
     "ClinVar and ReNOVo point in opposite directions"),
]


# ── payload ───────────────────────────────────────────────────────────────────
def build_payload(df, main_cols, detail_cols, flags, prio, groups):
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
        "groups": groups,
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
    unobserved = []
    for i in idx:
        a = af.iloc[i]
        if a != a or a is None:
            bands["not observed"] += 1
            unobserved.append(i)
        elif a < 1e-4:
            bands["under 0.01%"] += 1
        elif a < 1e-3:
            bands["0.01% to 0.1%"] += 1
        else:
            bands["0.1% to 1%"] += 1

    return {
        "unobserved": unobserved,
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
[hidden] { display: none !important; }

/* ── overview ─────────────────────────────────────────────────────────────── */
/* Findings on the left, the shape of the review set on the right. The charts sit
   beside the findings rather than under them so the first screen carries both the
   list to act on and the context to read it against. */
.overview {
  display: grid; align-items: start; gap: 1.75rem 2.5rem;
  grid-template-columns: minmax(0, 1.35fr) minmax(280px, 0.65fr);
  padding: 1.5rem 1.5rem 2rem;
  background: var(--surface);
}
.ov-head h2 {
  font-family: var(--font-serif); font-size: var(--step-3); font-weight: 600;
}
.findings-sub {
  margin-top: 0.35rem; color: var(--ink-muted);
  font-size: var(--step-0); max-width: 72ch; text-wrap: pretty;
}
.findings-sub b { color: var(--ink); font-variant-numeric: tabular-nums; }

/* ── priority findings ────────────────────────────────────────────────────── */
.priority { display: flex; flex-direction: column; gap: 1.5rem; margin-top: 1.5rem; }
.priority-group { border-top: 1px solid var(--border); padding-top: 0.85rem; }
.priority-head {
  display: grid; grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: baseline; gap: 0.65rem; width: 100%;
  padding: 0.2rem 0.4rem 0.35rem; margin-left: -0.4rem;
  background: none; border: 0; border-radius: var(--radius);
  font: inherit; text-align: left; cursor: pointer;
}
.priority-head:hover { background: var(--surface-sunken); }
.priority-head:hover .priority-open { color: var(--accent); text-decoration: underline; }
.priority-n {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step-2); font-weight: 600; line-height: 1;
  min-width: 3ch; text-align: right;
}
.priority-group[data-tone="p"]   .priority-n { color: var(--sig-p); }
.priority-group[data-tone="lp"]  .priority-n { color: var(--sig-lp); }
.priority-group[data-tone="acc"] .priority-n { color: var(--accent); }
.priority-title { font-size: var(--step-1); font-weight: 600; }
.priority-open {
  font-size: var(--step--1); color: var(--accent); white-space: nowrap;
}
.priority-why {
  font-size: var(--step--1); color: var(--ink-muted);
  margin: -0.15rem 0 0.55rem 3.65rem;
}
.finding {
  display: grid;
  grid-template-columns: minmax(6ch, max-content) minmax(0, 1fr) auto auto;
  align-items: baseline; gap: 0.15rem 0.6rem; width: 100%;
  padding: 0.35rem 0.4rem; margin-left: -0.4rem;
  background: none; border: 0; border-radius: var(--radius);
  font: inherit; text-align: left; cursor: pointer;
}
.finding + .finding { border-top: 1px solid var(--border); }
.finding:hover { background: var(--surface-sunken); }
.finding-gene { font-weight: 700; white-space: nowrap; }
.finding-change {
  font-family: var(--font-mono); font-size: var(--step--1); color: var(--ink-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
/* The disease is the answer to "pathogenic for what", so it gets its own line
   rather than being squeezed into the row. Flush left, not indented to the change
   column: that column's start moves with the gene symbol's length, so indenting
   left the disease lines ragged down the list. */
.finding-disease {
  grid-column: 1 / -1; font-size: var(--step--1);
  color: var(--ink); text-wrap: pretty;
}
.finding-disease.absent { color: var(--ink-muted); font-style: italic; }
.priority-more { font-size: var(--step--1); color: var(--ink-muted); margin-top: 0.45rem; }
.priority-none { font-size: var(--step-0); color: var(--ink-muted); margin-top: 1rem; }
.ov-actions { margin-top: 1.75rem; }

/* ── charts ───────────────────────────────────────────────────────────────── */
/* Sticky, because the findings column is much taller than this one: the profile of
   the review set stays on screen while a reader works down the list rather than
   scrolling away and leaving half the page empty. */
.charts {
  display: flex; flex-direction: column; gap: 1.5rem;
  position: sticky; top: 4.75rem;
}
.chart {
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 0.9rem 1rem 1rem; background: var(--surface);
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
/* The active group filter is a removable object, not a mode you have to remember
   you are in: it names itself and carries the control that clears it. */
#filterChip {
  display: inline-flex; align-items: center; gap: 0.45rem;
  padding: 0.2rem 0.3rem 0.2rem 0.6rem;
  font-size: var(--step--1);
  background: var(--accent-weak); color: var(--accent);
  border: 1px solid var(--accent-ring); border-radius: 999px;
}
#filterChip button {
  font: inherit; line-height: 1; cursor: pointer; color: inherit;
  background: none; border: 0; border-radius: 999px; padding: 0.15rem 0.35rem;
}
#filterChip button:hover { background: var(--surface); }

/* ── variant detail dialog ────────────────────────────────────────────────── */
/* A plain overlay rather than <dialog>: these open on lab desktops whose browser
   is whatever the institution froze, and showModal() is not universally there. */
.modal-backdrop {
  position: fixed; inset: 0; z-index: var(--z-modal);
  display: flex; align-items: flex-start; justify-content: center;
  padding: 5vh 1rem; overflow: auto;
  background: oklch(0.26 0.012 255 / 0.45);
}
.modal-card {
  width: min(560px, 100%);
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  box-shadow: 0 18px 48px oklch(0.26 0.012 255 / 0.22);
  padding: 1.25rem 1.4rem 1.4rem;
}
.modal-close {
  position: absolute; top: 0.6rem; right: 0.7rem;
  font: inherit; font-size: var(--step-1); line-height: 1; cursor: pointer;
  background: none; border: 0; color: var(--ink-muted); padding: 0.25rem 0.4rem;
  border-radius: var(--radius);
}
.modal-close:hover { background: var(--surface-sunken); color: var(--ink); }
.modal-card { position: relative; }
/* The dialog is wide enough to set the evidence as a real two-column term list;
   the docked panel is not, so it keeps the stacked one-column form. */
.modal-card .detail dl {
  grid-template-columns: minmax(120px, 0.7fr) minmax(0, 1.6fr);
  column-gap: 1.25rem; row-gap: 0.55rem; align-items: baseline;
}
.modal-card .detail dt { margin-bottom: 0; }
.result-count {
  margin-left: auto;
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step--1); color: var(--ink-muted);
}

/* ── table + panel ────────────────────────────────────────────────────────── */
.workspace { display: flex; align-items: stretch; min-height: 0; }
.table-region { flex: 1 1 auto; min-width: 0; }
/* max-height rather than height: a filtered view of two rows should not leave two
   thirds of a screen of empty table under it. The virtual scroller reads
   clientHeight, which converges either way because the pad rows carry the real
   height of the row set. */
#scroller {
  height: auto; max-height: 72vh; min-height: 180px;
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

/* ── variant detail ───────────────────────────────────────────────────────── */
/* One block of markup, two homes: docked beside the table, where arrow keys walk
   the list without the page reflowing, and inside the dialog the findings open. */
.panel {
  flex: 0 0 380px; max-width: 380px;
  max-height: 72vh; min-height: 180px;
  overflow: auto; background: var(--surface); padding: 1rem 1.25rem;
}
.panel-empty { color: var(--ink-muted); font-size: var(--step-0); }
.panel-empty kbd {
  font-family: var(--font-mono); font-size: var(--step--1);
  padding: 0.05rem 0.3rem; border: 1px solid var(--border-strong);
  border-radius: 3px; background: var(--surface-sunken);
}
.detail h3 {
  font-family: var(--font-serif); font-size: var(--step-2); font-weight: 600;
  margin-bottom: 0.15rem; padding-right: 2rem;
}
.panel-gdna {
  font-family: var(--font-mono); font-size: var(--step--1);
  color: var(--ink-muted); word-break: break-all; margin-bottom: 0.75rem;
}
.panel-chips { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 1rem; }
.detail dl { display: grid; grid-template-columns: minmax(0,1fr); gap: 0.6rem; }
.detail dt {
  font-size: var(--step--1); color: var(--ink-muted); margin-bottom: 0.1rem;
}
.detail dd {
  font-family: var(--font-mono); font-size: var(--step--1);
  word-break: break-word; white-space: pre-wrap;
}
.detail dd.plain { font-family: var(--font-sans); }
.detail dd.absent { font-family: var(--font-sans); color: var(--ink-muted); font-style: italic; }
.panel-links { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 1rem; }
.panel-links a {
  font-size: var(--step--1); padding: 0.25rem 0.55rem;
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  text-decoration: none; color: var(--accent);
}
.panel-links a:hover { background: var(--accent-weak); }

@media (max-width: 1100px) {
  .workspace { flex-direction: column; }
  .panel { flex: 1 1 auto; max-width: none; max-height: none; border-top: 1px solid var(--border); }
  #scroller { max-height: 60vh; border-right: none; }
}

@media (max-width: 980px) {
  .overview { grid-template-columns: minmax(0, 1fr); }
  .charts { flex-direction: row; flex-wrap: wrap; }
  .chart { flex: 1 1 260px; }
}

@media print {
  .no-print, #view-table { display: none !important; }
  .overview { grid-template-columns: minmax(0, 1.35fr) minmax(240px, 0.65fr); }
  .priority-open { display: none; }
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

  // CLNDN answers "pathogenic for what". It arrives underscored, with terms joined by
  // commas while the terms themselves contain commas ("Encephalopathy,_acute,_..."),
  // so a separator comma is one not followed by an underscore. Mirrors
  // disease_terms() in build_annotate_report.py.
  var DISEASE_NOISE = {
    "not provided": 1, "not specified": 1, "none provided": 1,
    "inborn genetic diseases": 1, "see cases": 1, "human phenotype ontology": 1,
    "association": 1, "other": 1
  };
  function diseaseList(v) {
    if (absent(v)) return [];
    var out = [], seen = {};
    String(v).split(/,(?!_)/).forEach(function (t) {
      t = t.replace(/_/g, " ").trim().replace(/,$/, "").trim();
      var k = t.toLowerCase();
      if (!t || seen[k] || DISEASE_NOISE[k]) return;
      seen[k] = 1;
      out.push(t);
    });
    return out;
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
  // Non-null when the table was opened from a findings block: the table then shows
  // exactly the variants behind that block and says so.
  var groupKey = null, groupSet = null;

  var SEARCH_KEYS = ["Hugo_Symbol", "genome_change", "HGVSc", "HGVSp_VEP"];

  function rebuild() {
    var n = P.n, review = P.review, out = [];
    var q = query.trim().toLowerCase();
    var searchCols = q ? SEARCH_KEYS.map(col) : null;

    for (var i = 0; i < n; i++) {
      if (groupSet) { if (!groupSet[i]) continue; }
      else if (view === "review" && !review[i]) continue;
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

  // ── variant detail ───────────────────────────────────────────────────────
  // One renderer, two homes: the panel docked beside the table and the dialog the
  // findings on the overview open.
  function detailHTML(i) {
    var gene = col("Hugo_Symbol")[i], gdna = col("genome_change")[i];
    var parts = ['<div class="detail">'];
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
      if (d.k === "CLNDN") {
        var ds = diseaseList(v);
        parts.push(ds.length
          ? '<dd class="plain">' + esc(ds.join(" · ")) + "</dd>"
          : '<dd class="absent">not reported</dd>');
        return;
      }
      if (d.k === "MAX_AF") { parts.push("<dd>" + afCell(v) + "</dd>"); return; }
      // ClinVar packs several MIM numbers into one field, joined with '|'.
      if (d.k === "clinvar_OMIM_id") {
        parts.push("<dd>" + esc(String(v).split(/[,|]/).join(" · ")) + "</dd>");
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
      // ClinVar packs several MIM numbers per variant and joins them with '|'.
      String(omim).split(/[,|]/).forEach(function (id) {
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
    parts.push("</div>");
    return parts.join("");
  }

  function select(i) {
    selected = i;
    var panel = document.getElementById("panel");
    panel.innerHTML = i < 0
      ? '<p class="panel-empty">Select a variant to see its full evidence.<br><br>' +
        'Use <kbd>&uarr;</kbd> and <kbd>&darr;</kbd> to walk the list without losing your place.</p>'
      : detailHTML(i);
    render();
  }

  // ── dialog ───────────────────────────────────────────────────────────────
  var modal = document.getElementById("modal");
  var modalBody = document.getElementById("modalBody");
  var modalClose = document.getElementById("modalClose");
  var lastFocus = null;

  function openModal(i) {
    lastFocus = document.activeElement;
    modalBody.innerHTML = detailHTML(i);
    modal.hidden = false;
    modalClose.focus();
  }

  function closeModal() {
    if (modal.hidden) return;
    modal.hidden = true;
    modalBody.innerHTML = "";
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  modalClose.addEventListener("click", closeModal);
  // Only a click on the backdrop itself closes; a click inside the card must not.
  modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });

  // ── events ───────────────────────────────────────────────────────────────
  scroller.addEventListener("scroll", render, { passive: true });
  window.addEventListener("resize", render);

  tbody.addEventListener("click", function (e) {
    var tr = e.target.closest("tr[data-row]");
    if (tr) select(parseInt(tr.dataset.row, 10));
  });

  // ── views ────────────────────────────────────────────────────────────────
  // The table is a second page rather than the bottom of the first one. Opening a
  // report should present findings; the 68,000-row surface is deliberately a step
  // away, and it does not exist in the layout until it is asked for.
  var overviewView = document.getElementById("view-overview");
  var tableView = document.getElementById("view-table");
  var chip = document.getElementById("filterChip");

  function showView(which) {
    var toTable = which === "table";
    overviewView.hidden = toTable;
    tableView.hidden = !toTable;
    window.scrollTo(0, 0);
    if (toTable) render();          // the scroller has no height while hidden
  }

  function setGroup(key) {
    groupKey = key;
    groupSet = null;
    if (key && P.groups && P.groups[key]) {
      groupSet = {};
      P.groups[key].forEach(function (i) { groupSet[i] = 1; });
    }
    // The two view buttons stay live while a findings filter is on: clicking one is
    // the obvious way out of the filter, and a disabled control that looks identical
    // to an enabled one on this toolbar's ground is worse than no control.
    Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (b) {
      b.setAttribute("aria-pressed", String(!groupKey && b.dataset.view === view));
    });
    if (groupKey) {
      var label = document.querySelector('[data-group="' + groupKey + '"]');
      chip.innerHTML = "Showing: " + esc(label ? label.dataset.groupLabel : groupKey) +
        ' <button type="button" id="clearFilter" aria-label="Clear this filter">&times;</button>';
      chip.hidden = false;
      document.getElementById("clearFilter").addEventListener("click", function () {
        setGroup(null);
        rebuild();
      });
    } else {
      chip.hidden = true;
      chip.innerHTML = "";
    }
  }

  // A finding on the overview opens that variant's evidence and nothing else.
  Array.prototype.forEach.call(document.querySelectorAll("[data-goto]"), function (btn) {
    btn.addEventListener("click", function () {
      openModal(parseInt(btn.dataset.goto, 10));
    });
  });

  // A findings block header opens the table filtered to exactly that block.
  Array.prototype.forEach.call(document.querySelectorAll("[data-group]"), function (btn) {
    btn.addEventListener("click", function () {
      query = "";
      document.getElementById("search").value = "";
      setGroup(btn.dataset.group);
      rebuild();
      showView("table");
      select(-1);
    });
  });

  document.getElementById("openTable").addEventListener("click", function () {
    setGroup(null);
    rebuild();
    showView("table");
  });

  document.getElementById("backToOverview").addEventListener("click", function () {
    showView("overview");
  });

  document.getElementById("search").addEventListener("input", function (e) {
    query = e.target.value;
    rebuild();
  });

  Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (btn) {
    btn.addEventListener("click", function () {
      view = btn.dataset.view;
      setGroup(null);
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
    if (e.key === "Escape") { closeModal(); return; }
    if (!modal.hidden || tableView.hidden) return;
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
  setGroup(null);
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

<main class="view" id="view-overview">
  <section class="overview">
    <div class="ov-main">
      <div class="ov-head">
        <h2>Findings</h2>
        <p class="findings-sub">__LEDE_SUB__</p>
      </div>
      <div class="priority">__PRIORITY__</div>
      <div class="ov-actions no-print">
        <button class="btn" type="button" id="openTable">Open the variant table &rarr;</button>
      </div>
    </div>
    <aside class="charts" aria-label="Shape of the review set">
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
    </aside>
  </section>
</main>

<main class="view" id="view-table" hidden>
  <div class="controls no-print">
    <button class="btn" type="button" id="backToOverview">&larr; Findings</button>
    <div class="controls-sep" aria-hidden="true"></div>
    <div class="controls-group" role="group" aria-label="Which variants to show">
      <button class="btn" type="button" data-view="review" aria-pressed="true">Review set</button>
      <button class="btn" type="button" data-view="all" aria-pressed="false">All variants</button>
    </div>
    <span id="filterChip" hidden></span>
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
</main>

<div class="modal-backdrop no-print" id="modal" hidden>
  <div class="modal-card" role="dialog" aria-modal="true" aria-label="Variant detail">
    <button class="modal-close" type="button" id="modalClose" aria-label="Close">&times;</button>
    <div id="modalBody"></div>
  </div>
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


def _pick_preview(df, indices, limit=6, per_gene=2):
    """Choose which rows of a group to show, preferring distinct genes.

    A group of 175 can begin with six indels in one gene (CFAP58 on patient 5724, a
    cluster in one 60 bp window). Showing all six spends the whole preview on one
    locus and tells the reader nothing about the other 169, so the preview takes at
    most two per gene and backfills only if that leaves it short.
    """
    if "Hugo_Symbol" not in df.columns:
        return indices[:limit]
    genes = df["Hugo_Symbol"]
    picked, counts, rest = [], {}, []
    for i in indices:
        g = str(genes.iloc[i])
        if counts.get(g, 0) < per_gene:
            counts[g] = counts.get(g, 0) + 1
            picked.append(i)
            if len(picked) == limit:
                return picked
        else:
            rest.append(i)
    return picked + rest[:limit - len(picked)]


def _finding_rows(df, indices, limit=6):
    """Compact clickable rows for a findings block. Clicking one opens its evidence.

    The disease line is the reason this is a two-line row: "CPT2 p.Ser113Leu P" does
    not tell a reader what the variant is pathogenic *for*, which is the first thing
    they need in order to decide whether it is relevant to the case in front of them.
    """
    get = lambda col, i: (str(df[col].iloc[i]) if col in df.columns else ".")
    out = []
    for i in _pick_preview(df, indices, limit):
        gene = get("Hugo_Symbol", i)
        prot = get("HGVSp_VEP", i)
        gdna = get("genome_change", i)
        cvc, cvcode, cvnote = style.clinvar_chip(get("encoded_CLNSIG", i))
        rnc, rncode, rnnote = style.renovo_chip(get("RENOVO_Class", i))
        change = prot if prot not in (".", "nan", "") else gdna
        disease = disease_label(get("CLNDN", i))
        disease_html = (f'<span class="finding-disease">{html_escape(disease)}</span>'
                        if disease else
                        '<span class="finding-disease absent">no ClinVar disease recorded</span>')
        out.append(
            f'<button class="finding" type="button" data-goto="{i}">'
            f'<span class="finding-gene">{html_escape(gene if gene != "." else "—")}</span>'
            f'<span class="finding-change">{html_escape(change)}</span>'
            f'<span class="chip {cvc}"><b>{cvcode}</b><span class="sr-only"> ClinVar {cvnote}</span></span>'
            f'<span class="chip {rnc}"><b>{rncode}</b><span class="sr-only"> ReNOVo {rnnote}</span></span>'
            f'{disease_html}'
            "</button>"
        )
    return "".join(out)


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

    n_unobs = ov["bands"]["not observed"]
    lede_sub = (f'<b>{ov["n_review"]:,}</b> variants are in the review set, drawn from '
                f'<b>{stats["total"]:,}</b> annotated: rare, and either flagged by ClinVar or '
                f'protein-affecting. <b>{n_unobs:,}</b> of them are absent from gnomAD entirely. '
                f'Everything below is counted over that review set; open any block to see all of '
                f'its variants in the table.')

    # ── findings blocks, grouped by why a variant is here ────────────────────
    # Each block header is the control that opens the table filtered to that block,
    # so the number a reader sees and the rows they get are the same set by
    # construction rather than by two definitions that could drift.
    tones = {"flagged": "p", "escalated": "lp", "novel": "acc", "contested": "p"}
    blocks = []
    for key, title, why in GROUPS:
        items = ov[key]
        if not items:
            continue
        shown = min(len(items), 6)
        more = (f'<p class="priority-more">{len(items) - shown:,} more in this group</p>'
                if len(items) > shown else "")
        blocks.append(
            f'<section class="priority-group" data-tone="{tones[key]}">'
            f'<button class="priority-head" type="button" data-group="{key}" '
            f'data-group-label="{html_escape(title)}">'
            f'<span class="priority-n">{len(items):,}</span>'
            f'<span class="priority-title">{html_escape(title)}</span>'
            f'<span class="priority-open no-print">see all in table &rarr;</span>'
            f'</button>'
            f'<p class="priority-why">{html_escape(why)}</p>'
            f'{_finding_rows(df, items)}{more}</section>'
        )
    priority_html = "".join(blocks) or (
        '<p class="priority-none">Nothing in the review set is flagged by ClinVar or called '
        'pathogenic by ReNOVo. The full variant table is still one click away.</p>')

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
            .replace("__LEDE_SUB__", lede_sub)
            .replace("__PRIORITY__", priority_html)
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
    stats = summarise(df, flags)
    ov = overview(df, flags)
    # Groups come out of overview() in genomic order, which is arbitrary here. Order
    # them the way the table orders itself so the preview and the filtered table
    # agree about what comes first.
    for key, _, _ in GROUPS:
        ov[key] = sorted(ov[key], key=lambda i: -prio[i])
    groups = {key: ov[key] for key, _, _ in GROUPS}
    payload = build_payload(df, main_cols, detail_cols, flags, prio, groups)
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
