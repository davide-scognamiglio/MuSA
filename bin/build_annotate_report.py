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

Usage: build_annotate_report.py <patient_code> <use_vep_plugins> <offline> <skip_genebe>
                                [logo] [pipeline_version] [hpo_terms]
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

# Everything the evidence panel reads. Grouped there under headings rather than
# rendered as one flat list; DETAIL_SECTIONS below owns that arrangement.
DETAIL_COLUMNS = [
    ("HGVSc",                "cDNA"),
    ("HGVSp_VEP",            "Protein"),
    ("Consequence",          "All consequences"),
    ("IMPACT",               "VEP impact"),
    ("VARIANT_CLASS",        "Variant class"),
    ("MAX_AF",               "Max allele frequency"),
    ("MAX_AF_POPS",          "Max AF population"),
    ("CLNDN",                "ClinVar disease"),
    ("CLNDISDB",             "ClinVar disease references"),
    ("clinvar_id",           "ClinVar variation ID"),
    ("ALLELEID",             "ClinVar allele ID"),
    ("ClinVar_RS",           "dbSNP"),
    ("Existing_variation",   "Known identifiers"),
    ("clinvar_OMIM_id",      "OMIM"),
    ("MIM_disease",          "OMIM phenotypes"),
    ("Orphanet_disorder",    "Orphanet"),
    ("encoded_CLNREVSTAT",   "ClinVar review status"),
    ("ClinGen_GeneDisease_Disease",        "ClinGen gene-disease"),
    ("ClinGen_GeneDisease_MOI",            "Inheritance (ClinGen)"),
    ("ClinGen_GeneDisease_Classification", "Gene-disease validity"),
    ("gnomAD_pLI",           "gnomAD pLI"),
    ("gnomAD_LOEUF",         "gnomAD LOEUF"),
    ("PL_score",             "ReNOVo pathogenicity score"),
    ("PUBMED",               "PubMed"),
    ("ref_context",          "Reference context"),
    ("bioinfo_params",       "Call quality"),
    ("PhenotypeOrthologous_Mouse_phenotype", "Mouse orthologue phenotype"),
    ("PhenotypeOrthologous_Rat_phenotype",   "Rat orthologue phenotype"),
    # Present only when GeneBe ran (online mode).
    ("acmg_criteria",          "GeneBe ACMG criteria"),
    ("renovo_adj_acmg_score",  "GeneBe ACMG score"),
]

# The panel is read top to bottom while deciding whether a variant matters, so it is
# ordered the way that decision is made: what the change is, how rare it is, which
# disease and gene it belongs to, what the literature says, and only then the
# sequencing detail and the animal models.
DETAIL_SECTIONS = [
    ("The change",     ["HGVSc", "HGVSp_VEP", "Consequence", "IMPACT", "VARIANT_CLASS"]),
    ("Population",     ["MAX_AF", "MAX_AF_POPS"]),
    ("Disease",        ["CLNDN", "encoded_CLNREVSTAT", "ClinGen_GeneDisease_Disease",
                        "ClinGen_GeneDisease_MOI", "ClinGen_GeneDisease_Classification",
                        "MIM_disease", "Orphanet_disorder"]),
    ("Gene constraint", ["gnomAD_pLI", "gnomAD_LOEUF"]),
    ("Prediction",     ["PL_score", "acmg_criteria", "renovo_adj_acmg_score"]),
    # No "References" section: every accession in the MAF is rendered as a link at the
    # top of the panel instead, so listing the raw strings again would be noise.
    ("Call quality",   ["bioinfo_params", "ref_context"]),
    ("Model organisms", ["PhenotypeOrthologous_Mouse_phenotype",
                         "PhenotypeOrthologous_Rat_phenotype"]),
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
        "version":         args[5] if len(args) > 5 else "",
        "hpo":             args[6] if len(args) > 6 else "",
    }


# The samplesheet's hpo column, ';'-separated. Nextflow renders an absent value as
# the literal "null", so that has to be treated as absence rather than as a term.
def parse_hpo(value):
    v = (value or "").strip()
    if not v or v.lower() in ("null", "none", "nan", "."):
        return []
    return [t for t in (x.strip().upper() for x in re.split(r"[;,\s]+", v))
            if re.fullmatch(r"HP:\d{7}", t)]


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
# ClinVar classes a variant may hold and still be worth reviewing. Benign and likely
# benign are excluded outright: ClinVar having looked at a variant and called it benign
# is a reason to stop, not a reason to read on. NC stays because "ClinVar has never
# seen it" is the commonest state of a genuinely novel finding.
REVIEWABLE_CLINVAR = ("P", "LP", "VUS", "NC")


def review_flags(df):
    """Return a list of 0/1 per row: is this variant in the default review view?

    Definition: rare (MAX_AF < 1%, absent counts as rare) AND protein-affecting AND
    not called benign or likely benign by ClinVar.

    The ClinVar test used to be an *alternative* to the consequence test rather than a
    filter over it, so a variant ClinVar had called benign still entered the set on the
    strength of its consequence: 98 of patient 5510's 529 were B or LB. Making it a
    filter drops those and costs nothing — measured across four exomes, no ClinVar P or
    LP variant is lost, because every one of them is protein-affecting anyway.

    Measured on four clinical exomes this yields 374-767 variants out of 65,000-73,000.
    The intent is the set a reviewer actually works through, not a claim that nothing
    else matters, which is why the full set stays in the document and one control away.
    """
    af = df["MAX_AF"] if "MAX_AF" in df.columns else pd.Series([""] * len(df))
    sig = df["encoded_CLNSIG"] if "encoded_CLNSIG" in df.columns else pd.Series([""] * len(df))
    csq = df["Consequence"] if "Consequence" in df.columns else pd.Series([""] * len(df))

    af_num = pd.to_numeric(af, errors="coerce")
    rare = af_num.isna() | (af_num < 0.01)

    reviewable = sig.fillna("").map(
        lambda v: style.clinvar_chip(v)[1] in REVIEWABLE_CLINVAR)
    coding = csq.fillna("").map(style.is_protein_affecting)

    flags = (rare & reviewable & coding).astype(int).tolist()
    print(f"  Review set: {sum(flags):,} of {len(flags):,} variants", file=sys.stderr)
    return flags


# The four reasons a variant is worth a second look, in the order a reviewer wants
# them. One definition drives three things: the blocks on the overview, the filter
# the table opens under when a block is clicked, and the label of that filter.
GROUPS = [
    ("flagged",    "ClinVar pathogenic",
     "pathogenic or likely pathogenic in ClinVar"),
    ("lof",        "Loss of function in an established disease gene",
     "a high-impact change in a gene ClinGen ties to a disease with definitive or "
     "strong evidence"),
    ("biallelic",  "Homozygous or hemizygous",
     "no wild-type allele was called in this sample, which is what a recessive "
     "diagnosis needs"),
    ("escalated",  "ClinVar VUS, ReNOVo pathogenic",
     "uncertain to ClinVar, called pathogenic by MuSA"),
    ("novel",      "Not classified by ClinVar",
     "ReNOVo calls these pathogenic and ClinVar has never seen them"),
    ("contested",  "Calls contradict",
     "ClinVar and ReNOVo point in opposite directions"),
]

# GATK writes the call into the INFO string. AC of AN allele copies: equal means no
# reference allele was called, which is the single most decisive fact about a
# candidate in a recessive case and was previously buried mid-way through a
# 150-character run-on field.
_AC = re.compile(r"(?:^|;)AC=([\d.]+)")
_AN = re.compile(r"(?:^|;)AN=([\d.]+)")


def zygosity(value):
    if not value or str(value) in (".", "nan"):
        return ""
    ac, an = _AC.search(str(value)), _AN.search(str(value))
    if not ac or not an:
        return ""
    try:
        ac, an = float(ac.group(1)), float(an.group(1))
    except ValueError:
        return ""
    if an <= 0:
        return ""
    if an == 1:
        return "hemizygous"
    return "homozygous" if ac >= an else "heterozygous"


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
        "sections": [{"name": n, "keys": ks} for n, ks in DETAIL_SECTIONS],
    }


# Clinical priority ordering. The table sorts on this by default: a reviewer opening
# the report should land on the ClinVar pathogenic calls, not on alphabetical genes.
# Conflicting shares the VUS chip but outranks it here: submitters disagreeing about a
# variant is a stronger reason to look than nobody having decided.
SIG_RANK = {"P": 6, "LP": 5, "VUS": 3, "LB": 2, "B": 1, "NC": 0}
CONFLICT_RANK = 4

# ReNOVo's own codes, on the same five-step scale. "MuSA calls it pathogenic" means a
# high- or intermediate-confidence pathogenic call; a low-confidence call in either
# direction reads as VUS and is not treated as a call.
RENOVO_PATHOGENIC = ("P", "LP")
RENOVO_BENIGN = ("B", "LB")


def _clinvar_rank(value):
    return CONFLICT_RANK if style.is_conflicting(value) else SIG_RANK.get(
        style.clinvar_chip(value)[1], 0)


def priority_scores(df):
    """Per-row sort key: ClinVar rank first, then ReNOVo's, then rarity.

    Encoded as one number so the JS sorts on a plain array:
        clinvar_rank * 1000  +  renovo_rank * 100  +  rarity_bonus
    """
    sig = df["encoded_CLNSIG"] if "encoded_CLNSIG" in df.columns else pd.Series([""] * len(df))
    rnv = df["RENOVO_Class"] if "RENOVO_Class" in df.columns else pd.Series([""] * len(df))
    af = pd.to_numeric(df["MAX_AF"], errors="coerce") if "MAX_AF" in df.columns else pd.Series([None] * len(df))

    out = []
    for s, r, a in zip(sig.fillna(""), rnv.fillna(""), af):
        rare = 10 if (a != a or a is None) else (5 if a < 1e-4 else 0)   # a != a catches NaN
        out.append(_clinvar_rank(s) * 1000
                   + SIG_RANK.get(style.renovo_chip(r)[1], 0) * 100
                   + rare)
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
    P, B = RENOVO_PATHOGENIC, RENOVO_BENIGN

    novel = [i for i, c, r in zip(idx, cv, rn) if c == "NC" and r in P]
    # Both directions of disagreement, though only the first can currently fire: the
    # review set no longer admits ClinVar B or LB (see REVIEWABLE_CLINVAR), so the
    # second arm is empty unless that filter is widened again. Kept because the group
    # means "the two classifiers disagree", not "ClinVar says pathogenic".
    contested = [i for i, c, r in zip(idx, cv, rn)
                 if (c in ("P", "LP") and r in B) or (c in ("B", "LB") and r in P)]
    # Strictly P and LP. Conflicting is chipped VUS and stays with the uncertain
    # variants, so this block means exactly what its title says.
    flagged = [i for i, c in zip(idx, cv) if c in ("P", "LP")]
    escalated = [i for i, c, r in zip(idx, cv, rn) if c == "VUS" and r in P]

    # Two groups that come from the variant and the gene rather than from either
    # classifier, so they surface candidates no classifier has flagged yet.
    impact = df["IMPACT"].fillna("") if "IMPACT" in df.columns else pd.Series([""] * len(df))
    valid = (df["ClinGen_GeneDisease_Classification"].fillna("")
             if "ClinGen_GeneDisease_Classification" in df.columns
             else pd.Series([""] * len(df)))
    info = (df["bioinfo_params"].fillna("") if "bioinfo_params" in df.columns
            else pd.Series([""] * len(df)))

    lof = [i for i in idx
           if str(impact.iloc[i]).upper() == "HIGH"
           and str(valid.iloc[i]).strip().lower() in ("definitive", "strong")]
    biallelic = [i for i in idx
                 if zygosity(info.iloc[i]) in ("homozygous", "hemizygous")]

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
        "lof": lof,
        "biallelic": biallelic,
        "novel": novel,
        "contested": contested,
        "flagged": flagged,
        "escalated": escalated,
        "bands": bands,
        "n_review": len(idx),
    }


def summarise(df, flags):
    """Counts for the header band, all of them over the **review set**.

    The header used to count every annotated variant while the findings blocks below
    counted the review set, so the page could show "P 3" directly above "ClinVar
    flagged 2". Both numbers were true and the pair was still a contradiction on
    screen. One denominator now, stated once.
    """
    idx = [i for i, f in enumerate(flags) if f]
    sig = (df["encoded_CLNSIG"].fillna("") if "encoded_CLNSIG" in df.columns
           else pd.Series([""] * len(df)))
    rnv = (df["RENOVO_Class"].fillna("") if "RENOVO_Class" in df.columns
           else pd.Series([""] * len(df)))

    cv, rn = {}, {}
    conflicting = 0
    for i in idx:
        code = style.clinvar_chip(sig.iloc[i])[1]
        cv[code] = cv.get(code, 0) + 1
        if style.is_conflicting(sig.iloc[i]):
            conflicting += 1
        code = style.renovo_chip(rnv.iloc[i])[1]
        rn[code] = rn.get(code, 0) + 1

    keys = style.SIG_SCALE + ["NC"]
    return {
        "total": len(df),
        "review": len(idx),
        "clinvar": {k: cv.get(k, 0) for k in keys},
        "renovo": {k: rn.get(k, 0) for k in keys},
        "conflicting": conflicting,
    }


# ── page CSS ──────────────────────────────────────────────────────────────────
PAGE_CSS = """
[hidden] { display: none !important; }

/* ── inked band ───────────────────────────────────────────────────────────── */
/* The one large field of colour in either document, and the only place the palette
   is used decoratively rather than semantically. It earns that: a white masthead
   over a white working page gave the report no identity at all, and the band is
   also where the two classifiers can be shown as figures rather than as a row of
   labelled numbers. Every count in here is over the review set, so nothing in the
   band can contradict the findings below it. */
/* Two halves: the case on the left, what was found in it on the right. The case
   identity used to sit in the masthead beside the logo, which is the wrong place for
   it — the masthead identifies the software, the band identifies the patient. */
.band {
  display: grid; gap: 1.5rem 2rem; align-items: start;
  grid-template-columns: minmax(0, 0.75fr) minmax(0, 1.5fr) minmax(0, 0.85fr);
  padding: 1.4rem 1.5rem;
  background: var(--band); color: var(--band-ink);
}
.band-case, .band-stats {
  border-right: 1px solid var(--band-line); padding-right: 2rem;
}
.case-id {
  font-family: var(--font-display); font-size: var(--step-3); font-weight: 600;
  letter-spacing: -0.01em; margin-bottom: 0.6rem;
}
.case-meta {
  display: grid; grid-template-columns: max-content minmax(0, 1fr);
  gap: 0.15rem 0.9rem; font-size: var(--step--1);
}
.case-meta dt { color: var(--band-muted); }
.case-meta dd { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

/* HPO terms are the reason this case is being read at all, so they belong beside the
   patient rather than nowhere. Offline the report has the identifiers but not their
   names, so each one links out to the term. */
.case-hpo { margin-top: 0.9rem; }
.case-hpo-label {
  display: block; font-size: var(--step--1); color: var(--band-muted);
  margin-bottom: 0.35rem;
}
.case-hpo-terms { display: flex; flex-wrap: wrap; gap: 0.3rem; }
.case-hpo-terms a {
  font-family: var(--font-mono); font-size: var(--step--1);
  color: var(--band-link); text-decoration: none;
  padding: 0.1rem 0.4rem;
  border: 1px solid var(--band-line); border-radius: 3px;
}
.case-hpo-terms a:hover { border-color: var(--band-link); }
.case-hpo-none { font-size: var(--step--1); color: var(--band-muted); font-style: italic; }

.band-stats {
  display: grid; gap: 1.25rem 2.5rem; align-items: center;
  grid-template-columns: minmax(0, auto) minmax(0, 1fr);
}
.band-figure { display: grid; gap: 0.1rem; }
.band-n {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step-6); font-weight: 600; line-height: 0.95;
  letter-spacing: -0.02em;
}
.band-label { font-size: var(--step-1); font-weight: 600; }

/* ── findings index ───────────────────────────────────────────────────────── */
/* The blocks below, listed with their counts, as the way into them. It answers
   "what did this case turn up, and how much of it" before a single row is read, and
   it saves scrolling past four blocks to reach the fifth. */
.band-index { display: grid; gap: 0.1rem; align-content: start; }
.band-index-label {
  font-size: var(--step--1); color: var(--band-muted);
  margin-bottom: 0.35rem;
}
.index-item {
  display: grid; grid-template-columns: 3.5ch minmax(0, 1fr);
  align-items: baseline; gap: 0.6rem; width: 100%;
  padding: 0.28rem 0.4rem; margin-left: -0.4rem;
  background: none; border: 0; border-radius: var(--radius);
  font: inherit; color: inherit; text-align: left; cursor: pointer;
}
.index-item:hover { background: oklch(1 0 0 / 0.07); }
.index-item:hover .index-title { text-decoration: underline; }
.index-n {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step-1); font-weight: 700; text-align: right;
}
.index-item[data-tone="p"]   .index-n { color: var(--sig-p-lift); }
.index-item[data-tone="lp"]  .index-n { color: var(--sig-lp-lift); }
.index-item[data-tone="acc"] .index-n { color: var(--band-link); }
.index-title { font-size: var(--step--1); text-wrap: pretty; }
.band-index-none { font-size: var(--step--1); color: var(--band-muted); font-style: italic; }

.band-scales { display: grid; gap: 1rem; }
.scale-head {
  display: flex; align-items: baseline; gap: 0.6rem;
  margin-bottom: 0.35rem;
}
.scale-name {
  font-size: var(--step-0); font-weight: 600; letter-spacing: 0.01em;
}
.scale-meta { font-size: var(--step--1); color: var(--band-muted); }

/* Each class as its own bordered box with the count beside the code. Every class is
   equally visible whether it holds four variants or six hundred, which is the point:
   the four are the ones being looked for. */
.scale-keys { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.key {
  display: inline-flex; align-items: baseline; gap: 0.45rem;
  padding: 0.2rem 0.55rem;
  font-family: var(--font-mono); font-size: var(--step-0);
  font-variant-numeric: tabular-nums;
  border: 1px solid currentColor; border-radius: var(--radius);
}
.key b { font-weight: 700; letter-spacing: 0.03em; }
.key .key-n { color: var(--band-ink); font-weight: 500; }
.key.sig-p   { color: var(--sig-p-lift); }
.key.sig-lp  { color: var(--sig-lp-lift); }
.key.sig-vus { color: var(--sig-vus-lift); }
.key.sig-lb  { color: var(--sig-lb-lift); }
.key.sig-b   { color: var(--sig-b-lift); }
/* Dashed, matching the chip convention: "not classified" is an absence, not a class. */
.key.sig-nc  { color: var(--sig-nc-lift); border-style: dashed; }

/* ── overview ─────────────────────────────────────────────────────────────── */
/* Findings on the left, the selected variant's evidence on the right. A reader
   triaging candidates has to see the list and one variant at the same time; a
   dialog covers exactly the thing being compared against. */
.overview {
  display: grid; align-items: start; gap: 2rem 2.5rem;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 430px);
  max-width: 1620px; margin-inline: auto;
  padding: 1.75rem 1.5rem 2.5rem;
  background: var(--surface);
}
.ov-detail {
  position: sticky; top: 1rem;
  max-height: calc(100vh - 2rem); overflow: auto;
  border: 1px solid var(--border); border-radius: var(--radius);
  padding: 1rem 1.15rem 1.25rem;
  background: var(--surface);
}
/* ── priority findings ────────────────────────────────────────────────────── */
/* Each block is its own bounded object. They were separated only by a hairline and a
   gap, which left five lists reading as one long list; a reader could not see where
   one reason to look ended and the next began. */
.priority { display: flex; flex-direction: column; gap: 1.75rem; margin-top: 1.5rem; }
.priority-group {
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  background: var(--surface); overflow: hidden;
  /* The masthead is sticky, so a block jumped to from the index would otherwise
     land with its header underneath it. */
  scroll-margin-top: 5rem;
}
.priority-head {
  display: grid; grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center; gap: 0.65rem; width: 100%;
  padding: 0.75rem 1rem 0.75rem 0.65rem;
  background: var(--surface-sunken);
  border: 0; border-bottom: 1px solid var(--border);
  font: inherit; text-align: left; cursor: pointer;
}
.priority-head:hover { background: var(--accent-weak); }
.priority-head:hover .priority-open { text-decoration: underline; }
.priority-n {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step-4); font-weight: 700; line-height: 1;
  min-width: 2.4ch; text-align: right; letter-spacing: -0.02em;
}
.priority-group[data-tone="p"]   .priority-n { color: var(--sig-p); }
.priority-group[data-tone="lp"]  .priority-n { color: var(--sig-lp); }
.priority-group[data-tone="acc"] .priority-n { color: var(--accent); }
.priority-title {
  font-family: var(--font-display);
  font-size: var(--step-2); font-weight: 600; letter-spacing: -0.01em;
  line-height: 1.2; text-wrap: balance;
}
.priority-open {
  font-size: var(--step--1); color: var(--accent); white-space: nowrap;
}
.priority-why {
  font-size: var(--step--1); color: var(--ink-muted);
  padding: 0.6rem 1rem 0; text-wrap: pretty;
}
/* Gene and disease are the headline of the row, on one line and at reading size:
   "CPT2 p.Ser113Leu P" never says what the variant is pathogenic *for*, and that is
   what decides whether it bears on the case. The coordinates drop to a second line
   as the supporting detail they are. */
.finding {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: baseline; gap: 0.2rem 0.75rem; width: 100%;
  padding: 0.6rem 1rem;
  background: none; border: 0;
  font: inherit; text-align: left; cursor: pointer;
}
.finding + .finding { border-top: 1px solid var(--border); }
.finding:first-of-type { border-top: 1px solid var(--border); margin-top: 0.6rem; }
.finding:hover { background: var(--surface-sunken); }
.finding[aria-current="true"] {
  background: var(--accent-weak);
  box-shadow: inset 3px 0 0 var(--accent);
}
/* The triage signals that decide whether a row is worth opening: impact, zygosity,
   absence from gnomAD, the gene's established relationship. Reading them off the
   list is the whole point of the list. */
.finding-tags {
  grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 0.2rem 0.5rem;
  font-size: var(--step--1); color: var(--ink-muted);
}
.finding-tags .tag { white-space: nowrap; }
.finding-tags .tag.on { color: var(--sig-p); font-weight: 600; }
.finding-tags .tag.gene { color: var(--ink); }
.finding-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 0.5rem; }
.finding-gene {
  font-size: var(--step-1); font-weight: 700; letter-spacing: -0.005em;
  white-space: nowrap;
}
.finding-disease { font-size: var(--step-0); color: var(--ink); text-wrap: pretty; }
.finding-disease.absent { color: var(--ink-muted); font-style: italic; }
.finding-more { color: var(--ink-muted); font-style: normal; }
.finding-change {
  grid-column: 1 / -1;
  font-family: var(--font-mono); font-size: var(--step--1); color: var(--ink-muted);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.priority-more {
  font-size: var(--step--1); color: var(--ink-muted);
  padding: 0.6rem 1rem; background: var(--surface-sunken);
  border-top: 1px solid var(--border);
}
.priority-none { font-size: var(--step-0); color: var(--ink-muted); margin-top: 1rem; }
.ov-actions { margin-top: 1.75rem; }

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
  font-family: var(--font-display); font-size: var(--step-3); font-weight: 600;
  margin-bottom: 0.15rem;
}
.detail-change {
  font-family: var(--font-mono); font-size: var(--step-0); font-weight: 400;
  color: var(--ink-muted);
}

/* The read of the evidence, above the evidence. Each line is one fact already
   interpreted, so the reader is not left holding eight fields in their head. */
.assess { list-style: none; display: grid; gap: 0.3rem; margin: 0.85rem 0 0.5rem; }
.assess li {
  position: relative; padding-left: 1.1rem;
  font-size: var(--step-0); text-wrap: pretty;
}
.assess li::before {
  content: "•"; position: absolute; left: 0.15rem;
  color: var(--ink-muted); font-weight: 700;
}
.assess li.hit { font-weight: 600; }
.assess li.hit::before  { content: "▸"; color: var(--sig-p); }
.assess li.warn::before { content: "!"; color: var(--sig-lp); }

.detail-sec { margin-top: 1.1rem; }
.detail-sec h4 {
  font-size: var(--step--1); font-weight: 600; letter-spacing: 0.04em;
  text-transform: uppercase; color: var(--ink-muted);
  padding-bottom: 0.25rem; margin-bottom: 0.5rem;
  border-bottom: 1px solid var(--border);
}
.detail .refs { display: flex; flex-wrap: wrap; gap: 0.3rem 0.5rem; }
.detail a.ref {
  font-family: var(--font-mono); font-size: var(--step--1);
  text-decoration: none; color: var(--accent);
  border-bottom: 1px solid var(--accent-ring);
}
.detail a.ref:hover { border-bottom-width: 2px; }
.detail details > summary { cursor: pointer; }
.detail details[open] > summary { margin-bottom: 0.3rem; color: var(--ink-muted); }

table.qual { border-collapse: collapse; width: 100%; }
table.qual th {
  text-align: left; font-weight: 400; color: var(--ink-muted);
  font-family: var(--font-sans); padding: 0.1rem 0.6rem 0.1rem 0;
  white-space: nowrap;
}
table.qual td {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  padding: 0.1rem 0;
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
.panel-links details { width: 100%; }
.panel-links details summary {
  font-size: var(--step--1); color: var(--ink-muted); cursor: pointer;
}
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
  .overview { grid-template-columns: minmax(0, 1fr); }
  .ov-detail { position: static; max-height: none; }
}

@media (max-width: 1280px) {
  .band { grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.4fr); }
  .band-stats { border-right: 0; padding-right: 0; }
  .band-index { grid-column: 1 / -1; padding-top: 1.25rem; border-top: 1px solid var(--band-line); }
}

@media (max-width: 1000px) {
  .band, .band-stats { grid-template-columns: minmax(0, 1fr); }
  .band-case, .band-stats {
    border-right: 0; padding-right: 0;
    border-bottom: 1px solid var(--band-line); padding-bottom: 1.25rem;
  }
}

@media print {
  .no-print, #view-table { display: none !important; }
  .priority-open { display: none; }
  /* The band is the document's identity; it has to survive the printer. */
  .band { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
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
    else if (s.indexOf("conflict") >= 0) { cls = "sig-vus"; code = "VUS"; note = "conflicting interpretations"; }
    else if (s.indexOf("likely") >= 0 && s.indexOf("patho") >= 0) { cls = "sig-lp"; code = "LP"; note = "likely pathogenic"; }
    else if (s.indexOf("likely") >= 0 && s.indexOf("benign") >= 0) { cls = "sig-lb"; code = "LB"; note = "likely benign"; }
    else if (s.indexOf("patho") >= 0) { cls = "sig-p"; code = "P"; note = "pathogenic"; }
    else if (s.indexOf("benign") >= 0) { cls = "sig-b"; code = "B"; note = "benign"; }
    else if (s.indexOf("vus") >= 0 || s.indexOf("uncertain") >= 0) { cls = "sig-vus"; code = "VUS"; note = "uncertain significance"; }
    return { cls: cls, code: code, note: note };
  }

  // ReNOVo's six classes fold onto the same five-step scale ClinVar is read on, so a
  // reader comparing the two columns is not translating between vocabularies. Mirrors
  // RENOVO_SCALE in musa_report_style.py; the two must not drift.
  var RENOVO_SCALE = {
    "hp pathogenic": ["sig-p",   "P",   "ReNOVo pathogenic, high confidence"],
    "ip pathogenic": ["sig-lp",  "LP",  "ReNOVo pathogenic, intermediate confidence"],
    "lp pathogenic": ["sig-vus", "VUS", "ReNOVo pathogenic, low confidence"],
    "lp benign":     ["sig-vus", "VUS", "ReNOVo benign, low confidence"],
    "ip benign":     ["sig-lb",  "LB",  "ReNOVo benign, intermediate confidence"],
    "hp benign":     ["sig-b",   "B",   "ReNOVo benign, high confidence"]
  };
  function renovoChip(v) {
    if (absent(v)) return { cls: "sig-nc", code: "NC", note: "no ReNOVo call" };
    var hit = RENOVO_SCALE[String(v).replace(/\s+/g, " ").trim().toLowerCase()];
    if (!hit) return { cls: "sig-nc", code: v, note: v };
    return { cls: hit[0], code: hit[1], note: hit[2] };
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
  function clinvarStars(v) {
    var k = String(v).trim();
    return STARS.hasOwnProperty(k) ? { n: parseInt(k, 10), text: STARS[k] } : null;
  }
  // encoded_CLNREVSTAT is a 0-4 gold-star rating. A bare "2" tells a reader nothing.
  function starsHTML(v) {
    if (!STARS.hasOwnProperty(String(v).trim())) return null;
    var n = parseInt(v, 10);
    return '<span class="stars" aria-hidden="true">' +
           "★".repeat(n) + '<span class="stars-empty">' + "☆".repeat(4 - n) + "</span></span> " +
           '<span class="stars-note">' + esc(STARS[String(v).trim()]) + "</span>";
  }

  // src is set where the two chips sit side by side without a column heading to say
  // which classifier produced which; inside the table the header already does that.
  function chipHTML(c, src) {
    return '<span class="chip ' + c.cls + '">' +
           (src ? '<span class="chip-src">' + esc(src) + "</span>" : "") +
           "<b>" + esc(c.code) + "</b>" +
           '<span class="sr-only"> ' + esc(c.note) + "</span></span>";
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

  // ── identifiers ──────────────────────────────────────────────────────────
  // Every accession in the MAF is a dead end unless it is a link, and the fields
  // that carry them are inconsistent: clinvar_OMIM_id is populated on 1,781 of
  // 73,008 rows while CLNDISDB carries OMIM numbers on 18,113 and MIM_disease
  // embeds more as "[MIM:615413]Disease name". Collect from all three.
  function link(href, text, cls) {
    return '<a class="' + (cls || "ref") + '" href="' + href +
           '" target="_blank" rel="noopener noreferrer">' + esc(text) + "</a>";
  }
  function uniq(list) {
    var seen = {}, out = [];
    list.forEach(function (v) { if (v && !seen[v]) { seen[v] = 1; out.push(v); } });
    return out;
  }
  function grab(re, s) {
    var out = [], m;
    re.lastIndex = 0;
    while ((m = re.exec(String(s))) !== null) out.push(m[1]);
    return out;
  }

  function omimIds(i) {
    var direct = absent(col("clinvar_OMIM_id")[i]) ? [] :
      String(col("clinvar_OMIM_id")[i]).split(/[,|;\s]+/).filter(function (x) { return /^\d+$/.test(x); });
    return uniq(direct
      .concat(grab(/OMIM:(\d+)/g, col("CLNDISDB")[i] || ""))
      .concat(grab(/\[MIM:(\d+)\]/g, col("MIM_disease")[i] || "")));
  }
  function pubmedIds(i) {
    return uniq(grab(/(\d{5,8})/g, col("PUBMED")[i] || ""));
  }
  function rsIds(i) {
    return uniq(grab(/(rs\d+)/g, (col("ClinVar_RS")[i] || "") + " " + (col("Existing_variation")[i] || ""))
      .concat((String(col("ClinVar_RS")[i] || "").match(/^\d+$/) ? ["rs" + col("ClinVar_RS")[i]] : [])));
  }

  // The MAF's own identifiers, as a row of links.
  function referenceLinks(i) {
    var out = [], gdna = col("genome_change")[i];
    var cvid = col("clinvar_id")[i], allele = col("ALLELEID")[i];
    if (!absent(cvid)) {
      String(cvid).split(/[,|]/).forEach(function (id) {
        id = id.trim();
        if (id) out.push(link("https://www.ncbi.nlm.nih.gov/clinvar/variation/" + encodeURIComponent(id),
                              "ClinVar " + id));
      });
    } else if (!absent(allele)) {
      // No variation ID on this row, but the allele ID resolves to the same record.
      out.push(link("https://www.ncbi.nlm.nih.gov/clinvar/?term=" + encodeURIComponent(allele) + "%5Balleleid%5D",
                    "ClinVar allele " + allele));
    }
    rsIds(i).forEach(function (rs) {
      out.push(link("https://www.ncbi.nlm.nih.gov/snp/" + encodeURIComponent(rs), rs));
    });
    omimIds(i).forEach(function (id) {
      out.push(link("https://www.omim.org/entry/" + encodeURIComponent(id), "OMIM " + id));
    });
    uniq(grab(/MONDO:MONDO:(\d+)/g, col("CLNDISDB")[i] || "")).forEach(function (id) {
      out.push(link("https://monarchinitiative.org/MONDO:" + id, "MONDO " + id));
    });
    uniq(grab(/Orphanet:(\d+)/g, col("CLNDISDB")[i] || "")).forEach(function (id) {
      out.push(link("https://www.orpha.net/en/disease/detail/" + id, "Orphanet " + id));
    });
    // Existing_variation also carries COSMIC (COSV/COSM) and HGMD (CM/CD) accessions.
    grab(/(COS[VM]\d+)/g, col("Existing_variation")[i] || "").forEach(function (id) {
      out.push(link("https://cancer.sanger.ac.uk/cosmic/search?q=" + id, id));
    });
    pubmedIds(i).forEach(function (id) {
      out.push(link("https://pubmed.ncbi.nlm.nih.gov/" + id + "/", "PMID " + id));
    });
    var gene = col("Hugo_Symbol")[i];
    if (!absent(gene)) {
      out.push(link("https://gnomad.broadinstitute.org/gene/" + encodeURIComponent(gene) + "?dataset=gnomad_r4",
                    "gnomAD " + gene));
    }
    var fu = franklinURL(gdna);
    if (fu) out.push(link(fu, "Franklin"));
    return out;
  }

  // ── call quality ─────────────────────────────────────────────────────────
  // bioinfo_params is the INFO field as one string. The two things a reviewer
  // actually asks of it are the zygosity and whether there were enough reads to
  // believe the call, and both were buried in a 150-character run-on.
  function infoFields(v) {
    var out = {};
    if (absent(v)) return out;
    String(v).split(";").forEach(function (kv) {
      var eq = kv.indexOf("=");
      if (eq > 0) out[kv.slice(0, eq).trim()] = kv.slice(eq + 1).trim();
    });
    return out;
  }
  function zygosity(f) {
    var ac = parseFloat(f.AC), an = parseFloat(f.AN);
    if (isNaN(ac) || isNaN(an) || an <= 0) return "";
    if (an === 1) return "hemizygous";
    return ac >= an ? "homozygous" : "heterozygous";
  }

  // ── assessment ───────────────────────────────────────────────────────────
  // The panel used to be a flat dump of every column, leaving the reader to hold
  // eight fields in their head and decide. These are the same fields, read.
  function assessment(i) {
    var out = [];
    var cv = clinvarChip(col("encoded_CLNSIG")[i]), rn = renovoChip(col("RENOVO_Class")[i]);
    var pathoish = { P: 1, LP: 1 }, benignish = { B: 1, LB: 1 };

    if (pathoish[cv.code] && pathoish[rn.code]) {
      out.push(["hit", "ClinVar and ReNOVo both call this pathogenic."]);
    } else if ((pathoish[cv.code] && benignish[rn.code]) || (benignish[cv.code] && pathoish[rn.code])) {
      out.push(["warn", "The two classifiers contradict each other: ClinVar " + cv.code +
                        ", ReNOVo " + rn.code + "."]);
    } else if (cv.code === "NC" && pathoish[rn.code]) {
      out.push(["hit", "ClinVar has never classified this variant; ReNOVo calls it pathogenic."]);
    }

    var impact = col("IMPACT")[i], csq = firstConsequence(col("Consequence")[i]);
    if (impact === "HIGH") out.push(["hit", "High-impact change (" + csq + "), predicted to disrupt the protein."]);
    else if (impact === "MODERATE") out.push(["", "Moderate-impact change (" + csq + ")."]);
    else if (!absent(impact)) out.push(["", esc(impact.toLowerCase()) + "-impact change (" + csq + ")."]);

    var f = infoFields(col("bioinfo_params")[i]), z = zygosity(f);
    if (z === "homozygous" || z === "hemizygous") {
      out.push(["hit", "Called " + z + ": no wild-type allele in this sample."]);
    } else if (z) {
      out.push(["", "Called heterozygous."]);
    }
    var dp = parseFloat(f.DP);
    if (!isNaN(dp) && dp < 20) {
      out.push(["warn", "Only " + dp + " reads at this position; the call is weakly supported."]);
    }

    var af = col("MAX_AF")[i];
    if (absent(af)) out.push(["hit", "Absent from gnomAD."]);
    else {
      var fv = parseFloat(af), pop = col("MAX_AF_POPS")[i];
      var where = absent(pop) ? "" : " (" + String(pop).replace(/_/g, " ") + ")";
      out.push([fv < 1e-4 ? "hit" : "",
                "Max population frequency " + (fv < 1e-4 ? fv.toExponential(1) : fv.toPrecision(2)) +
                where + "."]);
    }

    var gene = col("Hugo_Symbol")[i];
    var gd = col("ClinGen_GeneDisease_Disease")[i], moi = col("ClinGen_GeneDisease_MOI")[i],
        val = col("ClinGen_GeneDisease_Classification")[i];
    if (!absent(gd)) {
      var MOI = { AD: "autosomal dominant", AR: "autosomal recessive", XL: "X-linked",
                  XLR: "X-linked recessive", XLD: "X-linked dominant", MT: "mitochondrial" };
      out.push([/Definitive|Strong/i.test(val || "") ? "hit" : "",
                gene + " has a " + (absent(val) ? "recorded" : String(val).toLowerCase()) +
                " gene-disease relationship with " + gd +
                (absent(moi) ? "" : " (" + (MOI[moi] || moi) + ")") + "."]);
    }

    // LOEUF is a confidence bound, so it reads in bands. The usual line for "highly
    // constrained" is 0.35; anything up to about 1 is still some constraint, and only
    // above 1 is the gene genuinely unconstrained. Calling 0.6 "tolerant" would be a
    // claim a reader might act on, and it would be wrong.
    var loeuf = parseFloat(col("gnomAD_LOEUF")[i]), pli = parseFloat(col("gnomAD_pLI")[i]);
    if (!isNaN(loeuf)) {
      var band = loeuf < 0.35 ? ["hit", "strongly constrained against loss of function"]
               : loeuf < 1.0  ? ["", "moderately constrained against loss of function"]
                              : ["", "not constrained against loss of function"];
      out.push([band[0], "The gene is " + band[1] + " (LOEUF " + loeuf + ")."]);
    } else if (!isNaN(pli)) {
      out.push([pli >= 0.9 ? "hit" : "",
                "gnomAD pLI " + pli.toPrecision(2) +
                (pli >= 0.9 ? ", loss-of-function intolerant." : ".")]);
    }

    var stars = clinvarStars(col("encoded_CLNREVSTAT")[i]);
    if (stars) out.push([stars.n >= 2 ? "hit" : "", "ClinVar review: " + stars.text + "."]);

    return out;
  }

  // ── variant detail ───────────────────────────────────────────────────────
  function renderValue(k, v, i) {
    if (k === "encoded_CLNREVSTAT") {
      var st = starsHTML(v);
      return '<dd class="plain">' + (st || esc(v)) + "</dd>";
    }
    if (k.indexOf("PhenotypeOrthologous") === 0) {
      // These run to 30+ comma-separated terms. Kept, but folded away.
      var items = uniq(String(v).split(",").map(function (t) {
        return t.trim().replace(/^_+/, "").replace(/_/g, " ");
      }));
      if (!items.length) return '<dd class="absent">not reported</dd>';
      var head = items.slice(0, 4).join(", ");
      if (items.length <= 4) return '<dd class="plain">' + esc(head) + "</dd>";
      return '<dd class="plain"><details><summary>' + esc(head) + " … " +
             (items.length - 4) + " more</summary>" + esc(items.join(", ")) + "</details></dd>";
    }
    if (k === "Consequence") {
      return '<dd class="plain">' + esc(String(v).split(/[,&]/).join(", ").replace(/_/g, " ")) + "</dd>";
    }
    if (k === "CLNDN") {
      var ds = diseaseList(v);
      return ds.length ? '<dd class="plain">' + esc(ds.join(" · ")) + "</dd>"
                       : '<dd class="absent">not reported</dd>';
    }
    if (k === "MIM_disease") {
      // "[MIM:615413]Spermatogenic failure 12;[MIM:600649]..." -> linked names.
      var bits = String(v).split(";").map(function (s) { return s.trim(); }).filter(Boolean);
      var html = bits.map(function (s) {
        var m = /^\[MIM:(\d+)\](.*)$/.exec(s);
        if (!m) return esc(s);
        return link("https://www.omim.org/entry/" + m[1], m[2].trim() || ("OMIM " + m[1]));
      }).join(" · ");
      return '<dd class="plain">' + html + "</dd>";
    }
    if (k === "Orphanet_disorder") {
      return '<dd class="plain">' + esc(uniq(String(v).split(";")).join(" · ")) + "</dd>";
    }
    if (k === "MAX_AF") return "<dd>" + afCell(v) + "</dd>";
    if (k === "MAX_AF_POPS") return '<dd class="plain">' + esc(String(v).replace(/_/g, " ")) + "</dd>";
    if (k === "IMPACT") return '<dd class="plain">' + esc(String(v).toLowerCase()) + "</dd>";
    if (k === "PUBMED") {
      return '<dd class="plain refs">' + pubmedIds(i).map(function (id) {
        return link("https://pubmed.ncbi.nlm.nih.gov/" + id + "/", id);
      }).join(" ") + "</dd>";
    }
    if (k === "clinvar_OMIM_id" || k === "CLNDISDB") {
      var ids = omimIds(i);
      if (!ids.length) return '<dd class="absent">not reported</dd>';
      return '<dd class="plain refs">' + ids.map(function (id) {
        return link("https://www.omim.org/entry/" + id, "OMIM " + id);
      }).join(" ") + "</dd>";
    }
    if (k === "clinvar_id") {
      return '<dd class="plain refs">' + String(v).split(/[,|]/).map(function (id) {
        id = id.trim();
        return id ? link("https://www.ncbi.nlm.nih.gov/clinvar/variation/" + id, id) : "";
      }).join(" ") + "</dd>";
    }
    if (k === "ALLELEID") {
      return '<dd class="plain refs">' +
        link("https://www.ncbi.nlm.nih.gov/clinvar/?term=" + encodeURIComponent(v) + "%5Balleleid%5D", v) +
        "</dd>";
    }
    if (k === "ClinVar_RS" || k === "Existing_variation") {
      var rs = rsIds(i);
      var other = String(v).split(",").map(function (s) { return s.trim(); })
        .filter(function (s) { return s && !/^rs\d+$/.test(s); });
      var html = rs.map(function (r) {
        return link("https://www.ncbi.nlm.nih.gov/snp/" + r, r);
      }).concat(other.map(esc)).join(" ");
      return '<dd class="plain refs">' + html + "</dd>";
    }
    if (k === "bioinfo_params") {
      var f = infoFields(v), z = zygosity(f);
      var rows = [];
      if (z) rows.push(["Zygosity", z + (f.AC && f.AN ? " (" + f.AC + " of " + f.AN + " alleles)" : "")]);
      if (f.DP) rows.push(["Read depth", f.DP + "×"]);
      if (f.QD) rows.push(["Quality by depth", f.QD]);
      if (f.MQ) rows.push(["Mapping quality", f.MQ]);
      if (f.FS) rows.push(["Strand bias (FS)", f.FS]);
      if (f.SOR) rows.push(["Strand odds ratio", f.SOR]);
      if (!rows.length) return "<dd>" + esc(v) + "</dd>";
      return '<dd class="plain"><table class="qual">' + rows.map(function (r) {
        return "<tr><th>" + esc(r[0]) + "</th><td>" + esc(r[1]) + "</td></tr>";
      }).join("") + "</table></dd>";
    }
    return "<dd>" + esc(v).replace(/,/g, ", ") + "</dd>";
  }

  var LABEL = {};
  P.detail.forEach(function (d) { LABEL[d.k] = d.label; });

  function detailHTML(i) {
    var gene = col("Hugo_Symbol")[i], gdna = col("genome_change")[i];
    var prot = col("HGVSp_VEP")[i];
    var parts = ['<div class="detail">'];
    parts.push("<h3>" + esc(absent(gene) ? "Unnamed gene" : gene) +
               (absent(prot) ? "" : ' <span class="detail-change">' + esc(prot) + "</span>") + "</h3>");
    parts.push('<p class="panel-gdna">' + esc(absent(gdna) ? "—" : gdna) + "</p>");
    parts.push('<div class="panel-chips">' +
      chipHTML(clinvarChip(col("encoded_CLNSIG")[i]), "ClinVar") +
      chipHTML(renovoChip(col("RENOVO_Class")[i]), "ReNOVo") + "</div>");

    var a = assessment(i);
    if (a.length) {
      parts.push('<ul class="assess">' + a.map(function (row) {
        return '<li class="' + row[0] + '">' + esc(row[1]) + "</li>";
      }).join("") + "</ul>");
    }

    // A well-annotated variant can carry forty accessions. The first ten identify it;
    // the rest are the disease ontologies restating each other, so they fold away.
    var refs = referenceLinks(i);
    if (refs.length > 10) {
      parts.push('<div class="panel-links">' + refs.slice(0, 10).join("") +
        "<details><summary>" + (refs.length - 10) + " more references</summary>" +
        '<span class="panel-links">' + refs.slice(10).join("") + "</span></details></div>");
    } else if (refs.length) {
      parts.push('<div class="panel-links">' + refs.join("") + "</div>");
    }

    P.sections.forEach(function (sec) {
      var body = [];
      sec.keys.forEach(function (k) {
        if (!LABEL.hasOwnProperty(k)) return;          // column absent from this MAF
        var v = col(k)[i];
        if (absent(v)) return;                          // nothing to say, so say nothing
        body.push("<dt>" + esc(LABEL[k]) + "</dt>" + renderValue(k, v, i));
      });
      if (!body.length) return;
      parts.push('<section class="detail-sec"><h4>' + esc(sec.name) + "</h4><dl>" +
                 body.join("") + "</dl></section>");
    });

    parts.push("</div>");
    return parts.join("");
  }

  // Both views show the evidence in a panel beside the list, never over it: a reader
  // comparing several candidates must be able to see the list and one variant at the
  // same time, and a dialog hides exactly the thing being compared against.
  var EMPTY_PANEL =
    '<p class="panel-empty">Select a variant to see its evidence.<br><br>' +
    'Use <kbd>&uarr;</kbd> and <kbd>&darr;</kbd> to walk the list without losing your place.</p>';

  function select(i, where) {
    selected = i;
    var html = i < 0 ? EMPTY_PANEL : detailHTML(i);
    var target = document.getElementById(where === "overview" ? "ovPanel" : "panel");
    target.innerHTML = html;
    if (where === "overview") target.scrollTop = 0;
    render();
  }

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

  // A finding on the overview fills the panel beside it. Nothing navigates.
  Array.prototype.forEach.call(document.querySelectorAll("[data-goto]"), function (btn) {
    btn.addEventListener("click", function () {
      Array.prototype.forEach.call(document.querySelectorAll("[data-goto]"), function (b) {
        b.setAttribute("aria-current", String(b === btn));
      });
      select(parseInt(btn.dataset.goto, 10), "overview");
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

  // The band's index jumps to a block on the findings page. It works from the table
  // view too, so it doubles as the way back to a specific block rather than to the
  // top of the page.
  Array.prototype.forEach.call(document.querySelectorAll("[data-jump]"), function (btn) {
    btn.addEventListener("click", function () {
      var target = document.getElementById(btn.dataset.jump);
      if (!target) return;
      if (!tableView.hidden) showView("overview");
      var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      target.scrollIntoView({ block: "start", behavior: reduce ? "auto" : "smooth" });
      target.querySelector(".priority-head").focus({ preventScroll: true });
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
    if (tableView.hidden) return;
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

  select(-1, "overview");
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
__FONTS__
__TOKENS__
__BASE_CSS__
__PAGE_CSS__
</style>
</head>
<body>

<header class="masthead">
  __MASTHEAD_ID__
</header>

<section class="band">
  <div class="band-case">
    <h1 class="case-id">Patient __PATIENT__</h1>
    <dl class="case-meta">
      <dt>Assembly</dt><dd>hg38</dd>
      <dt>Generated</dt><dd>__GENERATED__</dd>
      <dt>Mode</dt><dd>__MODE__</dd>
    </dl>
    __HPO__
  </div>
  <div class="band-stats">
    <div class="band-figure">
      <span class="band-n">__REVIEW__</span>
      <span class="band-label" title="Rare, protein-affecting, and not called benign or likely benign by ClinVar. Drawn from __TOTAL__ annotated, all of which are in this document.">variants in the review set</span>
    </div>
    <div class="band-scales">__SCALES__</div>
  </div>
  <nav class="band-index" aria-label="Findings blocks">__INDEX__</nav>
</section>

<main class="view" id="view-overview">
  <section class="overview">
    <div class="ov-main">
      <div class="priority">__PRIORITY__</div>
      <div class="ov-actions no-print">
        <button class="btn" type="button" id="openTable">Open the variant table &rarr;</button>
      </div>
    </div>
    <aside class="ov-detail" id="ovPanel" aria-live="polite" aria-label="Variant evidence"></aside>
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


<footer class="doc-footer">
  <span>MuSA &middot; multi-source variant annotation</span>
  <span class="doc-credit">Developed by
    <a href="https://davide-scognamiglio.github.io/" target="_blank" rel="noopener noreferrer">D. Scognamiglio</a>
    and
    <a href="https://orcid.org/0000-0001-7462-3874" target="_blank" rel="noopener noreferrer">E. Bonetti</a>
    at IRCCS Istituto Ortopedico Rizzoli, Bologna.</span>
</footer>

<script id="payload" type="application/json">__PAYLOAD__</script>
<script>
window.__MUSA__ = JSON.parse(document.getElementById("payload").textContent);
__PAGE_JS__
</script>
</body>
</html>
"""


SIG_WORDS = {
    "P": "pathogenic", "LP": "likely pathogenic", "VUS": "uncertain significance",
    "LB": "likely benign", "B": "benign", "NC": "not classified",
}
SIG_CLASS = {"P": "sig-p", "LP": "sig-lp", "VUS": "sig-vus",
             "LB": "sig-lb", "B": "sig-b", "NC": "sig-nc"}


def _scale_html(name, counts, meta=""):
    """One classifier as a row of labelled count chips.

    This was a proportional stacked bar. It was dropped because it was mostly one
    grey block: on the review set ClinVar has no classification for the large
    majority, so the segment carrying the four variants that matter was a 7px sliver
    while "never seen" filled the width. The figure spent all its ink on the least
    interesting fact and made the most interesting one invisible.
    """
    order = [k for k in style.SIG_SCALE + ["NC"] if counts.get(k)]
    if not order:
        return ""
    keys = "".join(
        f'<span class="key {SIG_CLASS[k]}"><b>{k}</b>'
        f'<span class="key-n">{counts[k]:,}</span>'
        f'<span class="sr-only"> {SIG_WORDS[k]}</span></span>' for k in order)
    return (
        f'<div class="scale"><div class="scale-head"><span class="scale-name">{name}</span>'
        f'<span class="scale-meta">{meta}</span></div>'
        f'<div class="scale-keys">{keys}</div></div>'
    )


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
        terms = disease_terms(get("CLNDN", i))
        if terms:
            head = terms[0]
            if len(head) > 78:
                head = head[:77].rstrip() + "…"
            extra = (f' <i class="finding-more">+{len(terms) - 1} more</i>'
                     if len(terms) > 1 else "")
            disease_html = f'<span class="finding-disease">{html_escape(head)}{extra}</span>'
        else:
            disease_html = '<span class="finding-disease absent">no ClinVar disease recorded</span>'
        coords = " · ".join(x for x in (prot, gdna) if x not in (".", "nan", ""))
        out.append(
            f'<button class="finding" type="button" data-goto="{i}">'
            f'<span class="finding-head">'
            f'<span class="finding-gene">{html_escape(gene if gene != "." else "—")}</span>'
            f'{disease_html}</span>'
            f'<span class="chip {cvc}"><span class="chip-src">ClinVar</span><b>{cvcode}</b>'
            f'<span class="sr-only"> {cvnote}</span></span>'
            f'<span class="chip {rnc}"><span class="chip-src">ReNOVo</span><b>{rncode}</b>'
            f'<span class="sr-only"> {rnnote}</span></span>'
            f'{_finding_tags(df, i)}'
            f'<span class="finding-change">{html_escape(coords)}</span>'
            "</button>"
        )
    return "".join(out)


_MOI_WORDS = {"AD": "dominant", "AR": "recessive", "XL": "X-linked",
              "XLR": "X-linked recessive", "XLD": "X-linked dominant",
              "MT": "mitochondrial", "SD": "semidominant"}


def _finding_tags(df, i):
    """The signals that decide whether a row is worth opening, read off the row.

    Deliberately short and few: impact, zygosity, absence from gnomAD, and whether
    the gene has an established disease relationship. A reviewer scanning the list
    should be able to pick the candidates without opening anything.
    """
    get = lambda col: (str(df[col].iloc[i]) if col in df.columns else ".")
    tags = []

    if get("IMPACT").upper() == "HIGH":
        tags.append(('<span class="tag on">high impact</span>'))

    z = zygosity(get("bioinfo_params"))
    if z in ("homozygous", "hemizygous"):
        tags.append(f'<span class="tag on">{z}</span>')

    af = get("MAX_AF")
    if af in (".", "nan", ""):
        tags.append('<span class="tag on">not in gnomAD</span>')
    else:
        try:
            tags.append(f'<span class="tag">AF {float(af):.2g}</span>')
        except ValueError:
            pass

    valid, moi = get("ClinGen_GeneDisease_Classification"), get("ClinGen_GeneDisease_MOI")
    if valid not in (".", "nan", ""):
        word = _MOI_WORDS.get(moi, moi if moi not in (".", "nan", "") else "")
        label = f"{valid.lower()} gene-disease" + (f", {word}" if word else "")
        tags.append(f'<span class="tag gene">{html_escape(label)}</span>')

    stars = style.clinvar_stars(get("encoded_CLNREVSTAT"))
    if stars and stars[0] >= 2:
        tags.append(f'<span class="tag">{"★" * stars[0]} ClinVar</span>')

    return f'<span class="finding-tags">{"".join(tags)}</span>' if tags else ""


def _hpo_html(terms):
    if not terms:
        return ('<div class="case-hpo"><span class="case-hpo-none">'
                'No phenotype terms in the samplesheet.</span></div>')
    links = "".join(
        f'<a href="https://hpo.jax.org/browse/term/{t}" target="_blank" '
        f'rel="noopener noreferrer">{t}</a>' for t in terms)
    word = "term" if len(terms) == 1 else "terms"
    return (f'<div class="case-hpo"><span class="case-hpo-label">Phenotype '
            f'({len(terms)} HPO {word})</span>'
            f'<div class="case-hpo-terms">{links}</div></div>')


def build_html_page(patient_code, payload, stats, ov, df, logo_b64, logo_mime, mode,
                    version="", hpo=(), assets_dir=None):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    masthead = style.masthead_id(logo_b64, logo_mime, version, "Variant review")

    n_conf = stats["conflicting"]
    scales = (
        _scale_html("ClinVar", stats["clinvar"],
                    f"{n_conf} conflicting" if n_conf else "")
        + _scale_html("ReNOVo", stats["renovo"], "MuSA's own classifier")
    )

    # ── findings blocks, grouped by why a variant is here ────────────────────
    # Each block header is the control that opens the table filtered to that block,
    # so the number a reader sees and the rows they get are the same set by
    # construction rather than by two definitions that could drift.
    tones = {"flagged": "p", "lof": "p", "biallelic": "lp", "escalated": "lp",
             "novel": "acc", "contested": "p"}
    blocks, index = [], []
    for key, title, why in GROUPS:
        items = ov[key]
        if not items:
            continue
        shown = min(len(items), 6)
        more = (f'<p class="priority-more">{len(items) - shown:,} more in this group</p>'
                if len(items) > shown else "")
        blocks.append(
            f'<section class="priority-group" id="g-{key}" data-tone="{tones[key]}">'
            f'<button class="priority-head" type="button" data-group="{key}" '
            f'data-group-label="{html_escape(title)}">'
            f'<span class="priority-n">{len(items):,}</span>'
            f'<span class="priority-title">{html_escape(title)}</span>'
            f'<span class="priority-open no-print">see all in table &rarr;</span>'
            f'</button>'
            f'<p class="priority-why">{html_escape(why)}</p>'
            f'{_finding_rows(df, items)}{more}</section>'
        )
        index.append(
            f'<button class="index-item" type="button" data-jump="g-{key}" '
            f'data-tone="{tones[key]}">'
            f'<span class="index-n">{len(items):,}</span>'
            f'<span class="index-title">{html_escape(title)}</span></button>'
        )
    priority_html = "".join(blocks) or (
        '<p class="priority-none">Nothing in the review set is flagged by ClinVar or called '
        'pathogenic by ReNOVo. The full variant table is still one click away.</p>')
    index_html = (
        '<span class="band-index-label">Findings</span>' + "".join(index) if index
        else '<span class="band-index-none">No findings blocks on this case.</span>')

    headers = "".join(
        f'<th scope="col" tabindex="0" data-key="{c["k"]}">{c["label"]}'
        f'<span class="sort-mark" aria-hidden="true">&#8597;</span></th>'
        for c in payload["main"]
    )

    return (PAGE_HTML
            .replace("__FONTS__", style.load_fonts(assets_dir))
            .replace("__TOKENS__", style.TOKENS)
            .replace("__BASE_CSS__", style.BASE_CSS)
            .replace("__PAGE_CSS__", PAGE_CSS)
            .replace("__PAGE_JS__", PAGE_JS)
            .replace("__PRIORITY__", priority_html)
            .replace("__INDEX__", index_html)
            .replace("__SCALES__", scales)
            .replace("__HPO__", _hpo_html(hpo))
            .replace("__NCOL__", str(len(payload["main"])))
            .replace("__HEADERS__", headers)
            .replace("__REVIEW__", f"{stats['review']:,}")
            .replace("__TOTAL__", f"{stats['total']:,}")
            .replace("__GENERATED__", now)
            .replace("__MODE__", mode)
            .replace("__MASTHEAD_ID__", masthead)
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
    hpo = parse_hpo(params["hpo"])
    print(f"  HPO terms      : {len(hpo)}"
          + (f" ({', '.join(hpo)})" if hpo else " (none in samplesheet)"), file=sys.stderr)

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
        version=params["version"],
        hpo=hpo,
        # The typefaces live beside the logo, in the same assets directory the module
        # already passes in, so no new argument has to be threaded through Nextflow.
        assets_dir=(os.path.dirname(params["logo_path"]) if params["logo_path"] else None),
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
