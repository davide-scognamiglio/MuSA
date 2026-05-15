#!/usr/bin/env python3
"""
MuSA · Annotate Reporter (Python)
Generates a patient variant-analysis HTML dashboard from MAF files.

Usage:
    annotate_reporter.py <patient_code> <use_vep_plugins> <offline> <skip_genebe> [logo.png]

About MAF filtering
-------------------
This script does NOT perform variant filtering.  That responsibility belongs
entirely to the upstream Nextflow pipeline steps, which write two files:

    <patient>.filtered.maf  – primary source (already filtered upstream)
    <patient>.raw.maf       – fallback used only when filtered MAF is header-only

The script simply picks the best available file and renders it as-is.
No rows are dropped here beyond what was already excluded upstream.
"""

import sys
import os
import base64
import datetime
import io
import re
import warnings

warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# ══════════════════════════════════════════════════════════════════════════════
#  THEME  (identical to build_setup_report.py)
# ══════════════════════════════════════════════════════════════════════════════
THEME = {
    "bg":           "#0b0d14",
    "surface":      "#121520",
    "surface2":     "#1a1f2e",
    "border":       "#2a2f42",
    "border2":      "#4a5070",
    "text":         "#e6e8f2",
    "muted":        "#9aa0b8",
    "ok":           "#3aad82",
    "ok_dim":       "#3aad821a",
    "ok_border":    "#3aad8255",
    "fail":         "#d94f5c",
    "fail_dim":     "#d94f5c15",
    "fail_border":  "#d94f5c55",
    "pend":         "#d4a43a",
    "pend_dim":     "#d4a43a15",
    "pend_border":  "#d4a43a55",
    "accent":       "#6c5fff",
    "font_display": "'Poppins', sans-serif",
    "font_body":    "'Poppins', sans-serif",
    "font_mono":    "'DM Mono', 'Courier New', monospace",
    "google_fonts": (
        "https://fonts.googleapis.com/css2?"
        "family=Poppins:ital,wght@0,300;0,400;0,500;0,600;0,700;1,300;1,400"
        "&family=DM+Mono:wght@400;500&display=swap"
    ),
    "radius": "8px",
}

# ══════════════════════════════════════════════════════════════════════════════
#  COLUMN CONFIGURATION
#
#  Keys are ORIGINAL MAF column names.
#  display_names maps original → pretty label used in the HTML table header.
#  Plots always receive df_raw and use original column names directly.
# ══════════════════════════════════════════════════════════════════════════════
COLUMN_CONFIG = {
    # Columns shown in the main table (order is preserved)
    "main": {
        "online": [
            "Hugo_Symbol", "HGVSc", "HGVSp_VEP",
            "encoded_CLNSIG", "renovo_adj_acmg_score", "clinvar_trait",
            "MAX_AF","PUBMED", "Franklin" # Franklin is computed, not in the MAF
        ],
        "offline": [
            "Hugo_Symbol", "HGVSc", "genome_change", "HGVSp_VEP",
            "encoded_CLNSIG", "MAX_AF",
            "PUBMED", "Franklin"
        ],
    },
    # Columns shown only in expandable child rows
    "details": {
        "with_plugins": [
            "genome_change","ref_context","bioinfo_params",
            "MAX_AF_POPS", "clinvar_OMIM_id","clinvar_id", 
            "acmg_criteria", "encoded_CLNREVSTAT",
            "PhenotypeOrthologous_Mouse_phenotype",
            "PhenotypeOrthologous_Rat_phenotype"
        ],
        "without_plugins": [
            "genome_change","ref_context","bioinfo_params",
            "clinvar_OMIM_id","clinvar_id", "acmg_criteria", "encoded_CLNREVSTAT"
        ],
    },
    # Pretty labels for table headers (original MAF name -> display name)
    "display_names": {
        "Hugo_Symbol":            "gene",
        "genome_change":          "gDNA",
        "ref_context":            "Reference context",
        "bioinfo_params":         "Variant quality",
        "HGVSp_VEP":              "a.a.",
        "Consequence":            "consequence",
        "encoded_CLNSIG": "Clinvar class",
        "renovo_adj_acmg_score":  "MuSA class",
        "acmg_criteria":          "GeneBe ACMG criteria",
        "MAX_AF":                 "max AF",
        "MAX_AF_POPS":            "max AF pop",
        "PL_score":               "Renovo score",
        "PUBMED":                 "PUBMED",
        "HGVSc":                  "cDNA",
        "Franklin":               "Franklin",
        "clinvar_OMIM_id":        "OMIM",
        "clinvar_id":        "Clinvar ID",
        "encoded_CLNREVSTAT": "Clinvar review",
        "clinvar_trait":          "Clinvar trait",
        "PhenotypeOrthologous_Mouse_phenotype": "Mouse phenotype",
        "PhenotypeOrthologous_Rat_phenotype":   "Rat phenotype",
    },
}

# Colour map for Consequence VALUES (used in both plots and table badges)
VC_COLOURS = {
    "Missense_Mutation":       "#6c5fff",
    "Nonsense_Mutation":       "#d94f5c",
    "Frame_Shift_Del":         "#d4a43a",
    "Frame_Shift_Ins":         "#e8855a",
    "In_Frame_Del":            "#3aad82",
    "In_Frame_Ins":            "#3a8fad",
    "Splice_Site":             "#ad3a82",
    "Silent":                  "#4a5070",
    "3'UTR":                   "#2a5070",
    "5'UTR":                   "#2a3d70",
    "Intron":                  "#333a52",
    "RNA":                     "#5a3370",
    "IGR":                     "#2a2f42",
    "Translation_Start_Site":  "#c45fff",
    "Nonstop_Mutation":        "#ff5f5f",
}


# ══════════════════════════════════════════════════════════════════════════════
#  CSS HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def css_vars(t: dict) -> str:
    mapping = {
        "bg": "bg", "surface": "surface", "surface2": "surface2",
        "border": "border", "border2": "border2", "text": "text",
        "muted": "muted", "ok": "ok", "ok_dim": "ok-dim",
        "ok_border": "ok-border", "fail": "fail", "fail_dim": "fail-dim",
        "fail_border": "fail-border", "pend": "pend", "pend_dim": "pend-dim",
        "pend_border": "pend-border", "accent": "accent",
        "font_display": "font-display", "font_body": "font-body",
        "font_mono": "font-mono", "radius": "radius",
    }
    lines = ["  :root {"]
    for key, css_name in mapping.items():
        lines.append(f"    --{css_name}: {t[key]};")
    lines.append("  }")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
#  LOGO
#  Accepted as an explicit CLI argument so the Nextflow module can pass
#  ${projectDir}/assets/MuSA_logo.png without relying on __file__ location.
# ══════════════════════════════════════════════════════════════════════════════
def load_logo_base64(logo_path: str):
    """Return (b64_string, mime_type) or (None, None) if path is invalid."""
    if not logo_path or not os.path.isfile(logo_path):
        if logo_path:
            print(f"  WARNING: Logo not found at: {logo_path}", file=sys.stderr)
        return None, None
    ext  = os.path.splitext(logo_path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "svg": "image/svg+xml",
            "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
    with open(logo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return b64, mime


# ══════════════════════════════════════════════════════════════════════════════
#  ARGUMENT PARSING
#
#  Args: patient_code  use_vep_plugins  offline  skip_genebe  [logo_path]
#  Note: 'workflow' has been removed — it is deprecated and no longer used.
# ══════════════════════════════════════════════════════════════════════════════
def parse_args():
    args = sys.argv[1:]
    if len(args) < 4:
        print(
            "Usage: annotate_reporter.py <patient_code> <use_vep_plugins> "
            "<offline> <skip_genebe> [logo_path]"
        )
        sys.exit(1)

    def _bool(v):
        return str(v).strip().upper() in ("TRUE", "1", "YES")

    return {
        "patient_code":    args[0],
        "use_vep_plugins": _bool(args[1]),
        "offline":         _bool(args[2]),
        "skip_genebe":     _bool(args[3]),
        "logo_path":       args[4] if len(args) > 4 else None,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  MAF READING
#
#  Filtering contract
#  ------------------
#  This script does NOT filter variants.  The pipeline produces two files:
#    * <patient>.filtered.maf  -- primary source (already filtered upstream)
#    * <patient>.raw.maf       -- fallback when filtered file is header-only
#  We pick whichever file has actual data and render it as-is.
# ══════════════════════════════════════════════════════════════════════════════
_HEADER_ONLY = object()   # sentinel — avoids DataFrame truthiness pitfalls


def _read_maf_file(path: str):
    """Return DataFrame, _HEADER_ONLY sentinel, or None on failure."""
    if not os.path.isfile(path):
        return None
    try:
        df = pd.read_csv(path, sep="\t", low_memory=False, dtype=str)
        df = df.loc[:, ~df.columns.duplicated()]
        if df.empty:
            return _HEADER_ONLY
        print(f"  Loaded {len(df):,} rows x {len(df.columns)} cols from {path}",
              file=sys.stderr)
        return df
    except Exception as exc:
        print(f"  WARNING: Could not read {path}: {exc}", file=sys.stderr)
        return None


def load_maf_data(patient_code: str) -> pd.DataFrame:
    filtered = f"{patient_code}.filtered.maf"
    raw      = f"{patient_code}.raw.maf"

    result = _read_maf_file(filtered)
    if result is _HEADER_ONLY or result is None:
        if result is _HEADER_ONLY:
            print("  Filtered MAF is header-only, falling back to raw MAF",
                  file=sys.stderr)
        result = _read_maf_file(raw)

    if result is None or result is _HEADER_ONLY:
        raise RuntimeError(f"No usable MAF found for patient '{patient_code}'")

    # Warn about any expected columns that are missing so users can diagnose issues
    expected = set(COLUMN_CONFIG["display_names"].keys()) - {"Franklin"}
    missing  = expected - set(result.columns)
    if missing:
        print(f"  WARNING: Columns not in MAF (will be skipped): "
              f"{', '.join(sorted(missing))}", file=sys.stderr)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  FRANKLIN URL BUILDER
# ══════════════════════════════════════════════════════════════════════════════
def make_franklin_url(genome_change: str) -> str:
    if not genome_change or pd.isna(genome_change) or genome_change.strip() == "":
        return ""
    gc = re.sub(r"^g\.", "", genome_change.strip())
    m  = re.match(r"chr([^:]+):", gc)
    if not m:
        return ""
    chrom = m.group(1)

    snv = re.search(r":([0-9]+)([ACGT])>([ACGT])$", gc)
    if snv:
        pos, ref, alt = snv.group(1), snv.group(2), snv.group(3)
        return (f"https://franklin.genoox.com/clinical-db/variant/snp/"
                f"chr{chrom}-{pos}-{ref}-{alt}-hg38")

    ins = re.search(r":([0-9]+)_[0-9]+ins([ACGT]+)$", gc)
    if ins:
        pos, ins_seq = ins.group(1), ins.group(2)
        ref_m = re.search(r":([ACGT])_", gc)
        ref   = ref_m.group(1) if ref_m else "N"
        return (f"https://franklin.genoox.com/clinical-db/variant/snp/"
                f"chr{chrom}-{pos}-{ref}-{ref+ins_seq}-hg38")

    del_m = re.search(r":([0-9]+)_[0-9]+del([ACGT]*)$", gc)
    if del_m:
        pos, del_seq = del_m.group(1), del_m.group(2)
        ref = del_seq if del_seq else "N"
        alt = ref[0] if ref else "N"
        return (f"https://franklin.genoox.com/clinical-db/variant/snp/"
                f"chr{chrom}-{pos}-{ref}-{alt}-hg38")

    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  DATA PREPARATION
#
#  Returns:
#    df_display   -- renamed, subsetted DataFrame for the HTML table
#    main_display -- ordered list of display-name column headers (main table)
#    det_display  -- ordered list of display-name column headers (child rows)
#
#  Design: plots and stats are generated separately from df_raw using original
#  MAF column names, so they are completely independent of the display selection.
# ══════════════════════════════════════════════════════════════════════════════
def prepare_display_data(df: pd.DataFrame, offline: bool, use_vep_plugins: bool):
    cfg = COLUMN_CONFIG
    dn  = cfg["display_names"]

    main_src = list(cfg["main"]["offline"] if offline else cfg["main"]["online"])
    det_src  = list(cfg["details"]["with_plugins"] if use_vep_plugins
                    else cfg["details"]["without_plugins"])

    # Franklin is computed below; exclude it from the MAF column existence check
    franklin_requested = "Franklin" in main_src
    main_src_maf = [c for c in main_src if c != "Franklin" and c in df.columns]
    det_src      = [c for c in det_src if c in df.columns]

    # Work on a copy with NAs filled as empty strings
    df = df.copy().fillna("")
    # Normalize HGVSp_VEP: take first transcript if multiple (semicolon-separated)
    if "HGVSp_VEP" in df.columns:
        df["HGVSp_VEP"] = df["HGVSp_VEP"].apply(
            lambda x: x.split(";")[0] if x else x
        )
    # Compute Franklin URL from genome_change (original column name)
    if "genome_change" in df.columns and franklin_requested:
        df["Franklin"] = df["genome_change"].apply(make_franklin_url)
        main_src_final = main_src_maf + ["Franklin"]
    else:
        main_src_final = main_src_maf

    # Build the display subset in the configured column order
    all_src = main_src_final + [c for c in det_src if c not in main_src_final]
    subset  = df[[c for c in all_src if c in df.columns]].copy()

    # Rename columns to pretty display names
    rename_map = {col: dn.get(col, col.replace("_", " ")) for col in subset.columns}
    subset.rename(columns=rename_map, inplace=True)


    # Build ordered header lists for the table builder
    main_display = [rename_map[c] for c in main_src_final if c in rename_map]
    det_display  = [rename_map[c] for c in det_src        if c in rename_map]

    return subset, main_display, det_display


# ══════════════════════════════════════════════════════════════════════════════
#  CELL RENDERING  (HTML badges / links for specific display columns)
# ══════════════════════════════════════════════════════════════════════════════
def _render_max_af(val: str) -> str:
    if not val:
        return '<span class="af-badge private">Private</span>'
    try:
        f = float(val)
        if f > 0.05:
            return f'<span class="af-badge common">Common ({val})</span>'
        return f'<span class="af-badge rare">Rare ({val})</span>'
    except ValueError:
        return val


def _render_acmg(val) -> str:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return '<span class="acmg-badge vus">VUS</span>'
    if   f <= -7: cls, lbl = "benign",            f"B ({f:.2f})"
    elif f <= -1: cls, lbl = "likely-benign",     f"LB ({f:.2f})"
    elif f <=  5: cls, lbl = "vus",               f"VUS ({f:.2f})"
    elif f <=  9: cls, lbl = "likely-pathogenic", f"LP ({f:.2f})"
    else:         cls, lbl = "pathogenic",        f"P ({f:.2f})"
    return f'<span class="acmg-badge {cls}">{lbl}</span>'


def _render_clinvar(val: str) -> str:
    if not val:
        return ""
    vl = val.lower()
    if "pathogenic" in vl and "likely" not in vl and "benign" not in vl:
        cls, label = "cv-pathogenic", "P"
    elif "likely_pathogenic" in vl or "likely pathogenic" in vl:
        cls, label = "cv-likely-pathogenic", "LP"
    elif "benign" in vl and "likely" not in vl and "pathogenic" not in vl:
        cls, label = "cv-benign", "B"
    elif "likely_benign" in vl or "likely benign" in vl:
        cls, label = "cv-likely-benign", "LB"
    elif "uncertain" in vl or "vus" in vl:
        cls, label = "cv-vus", "VUS"
    elif "not classified" in vl:
        cls, label = "cv-notclassified", "NC"
    else:
        cls, label = "cv-other", val  # fallback: show raw
    return f'<span class="cv-badge {cls}">{label}</span>'


def _render_pubmed(val: str) -> str:
    if not val:
        return ""
    ids   = [x.strip() for x in str(val).split(",") if x.strip()]
    links = [
        f'<a class="pubmed-link" href="https://pubmed.ncbi.nlm.nih.gov/{i}/" '
        f'target="_blank">{i}</a>'
        for i in ids
    ]
    return ", ".join(links)


def _render_franklin(val: str) -> str:
    if not val:
        return ""
    return (f'<a class="franklin-link" href="{val}" target="_blank" '
            f'rel="noopener noreferrer">Link Franklin</a>')


def _render_omim(val: str) -> str:
    if not val:
        return ""

    ids = [x.strip() for x in str(val).split(",") if x.strip()]
    links = [
        f'<a class="omim-link" '
        f'href="https://www.omim.org/entry/{i}?search={i}&highlight={i}" '
        f'target="_blank" rel="noopener noreferrer">{i}</a>'
        for i in ids
    ]
    return ", ".join(links)

def _render_clinvar_id(val: str) -> str:
    if not val:
        return ""

    ids = [x.strip() for x in str(val).split(",") if x.strip()]
    links = [
        f'<a class="omim-link" '
        f'href="https://www.ncbi.nlm.nih.gov/clinvar/variation/{i}?term={i}&%5BVariation+ID%5D" '
        f'target="_blank" rel="noopener noreferrer">{i}</a>'
        for i in ids
    ]
    return ", ".join(links)

def _render_vc(val: str) -> str:
    if not val:
        return ""
    color = VC_COLOURS.get(val, THEME["border2"])
    return (f'<span class="vc-badge" style="border-color:{color};color:{color};">'
            f'{val.replace("_", " ")}</span>')


def _render_phenotype(val: str) -> str:
    if not val:
        return ""
    items = [i.strip().replace("_", " ") for i in val.split(",") if i.strip()]
    return ", ".join(dict.fromkeys(items))   # deduplicate, preserve order


_PHENOTYPE_DISPLAY = {"Mouse phenotype", "Rat phenotype"}


def _cell_html(col: str, val) -> str:
    """Convert a raw cell value to its rendered HTML string.
    col is the DISPLAY name (after renaming).
    For 'MuSA class' returns a (sort_key, html) tuple so the caller
    can emit  <td data-order="sort_key">html</td>  for correct numeric sorting."""
    s = "" if (pd.isna(val) or str(val) in ("nan", "None", "")) else str(val)
    if col == "max AF":           return _render_max_af(s)
    if col == "MuSA class":
        html = _render_acmg(s)
        try:
            sort_key = float(s)
        except (ValueError, TypeError):
            sort_key = -999.0   # put unparseable values at the bottom
        return (sort_key, html)
    if col == "Clinvar class":    return _render_clinvar(s)
    if col == "PUBMED":           return _render_pubmed(s)
    if col == "Franklin":         return _render_franklin(s)
    if col == "OMIM":             return _render_omim(s)
    if col == "Clinvar ID":       return _render_clinvar_id(s)
    if col == "type":             return _render_vc(s)
    if col in _PHENOTYPE_DISPLAY: return _render_phenotype(s)
    return s


# ══════════════════════════════════════════════════════════════════════════════
#  TABLE HTML  (DataTables.js, dark-themed)
# ══════════════════════════════════════════════════════════════════════════════
def build_table_html(df: pd.DataFrame, main_cols: list, det_cols: list) -> str:
    """
    Build a self-contained <table> + <script> block.
    df must already be renamed to display names.
    main_cols / det_cols are ordered lists of DISPLAY names.
    """
    main_cols = [c for c in main_cols if c in df.columns]
    det_cols  = [c for c in det_cols  if c in df.columns]
    has_child = bool(det_cols)

    # thead
    expand_th = "<th></th>" if has_child else ""
    th_html   = expand_th + "".join(f"<th>{c}</th>" for c in main_cols)

    # tbody
    rows_html = []
    for _, row in df.iterrows():
        cells = []
        if has_child:
            child_rows = "".join(
                f"<tr><td class='det-label'>{c}</td>"
                f"<td class='det-val'>{_cell_html(c, row.get(c, ''))}</td></tr>"
                for c in det_cols
            )
            child_html = (
                f"<table class='child-table'>"
                f"<colgroup><col style='width:160px'><col></colgroup>"
                f"{child_rows}</table>"
            )
            # Embed in data-attribute — escape double-quotes for HTML attribute context
            child_attr = child_html.replace('"', "&quot;")
            cells.append(f'<td class="expand-cell" data-child="{child_attr}">&#9654;</td>')
        for col in main_cols:
            rendered = _cell_html(col, row.get(col, ""))
            if isinstance(rendered, tuple):
                sort_key, html = rendered
                cells.append(f'<td data-order="{sort_key}">{html}</td>')
            else:
                cells.append(f"<td>{rendered}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    tbody_html = "\n".join(rows_html)

    # Default sort: prefer "suggested classification" desc, then "Renovo score" desc
    sort_idx = -1
    for cand in ("MuSA class", "Renovo score"):
        if cand in main_cols:
            sort_idx = main_cols.index(cand) + (1 if has_child else 0)
            break
    sort_js    = f"[{sort_idx}, 'desc']" if sort_idx >= 0 else "[0, 'asc']"
    no_sort_js = "{ orderable: false, targets: 0 }," if has_child else ""

    return f"""
<table id="variantTable" class="display compact nowrap" style="width:100%">
  <thead><tr>{th_html}</tr></thead>
  <tbody>{tbody_html}</tbody>
</table>
<script>
(function(){{
  const table = new DataTable('#variantTable', {{
    order: [{sort_js}],
    pageLength: 5,
    lengthMenu: [5, 10, 15, 25, 50],
    scrollX: true,
    autoWidth: false,
    columnDefs: [
      {{ targets: '_all', defaultContent: '' }},
      {no_sort_js}
    ],
    language: {{
      search: '',
      searchPlaceholder: 'Search variants\u2026',
      emptyTable: 'No variants match the current filter.',
      paginate: {{ first: '\u00ab', last: '\u00bb', next: '\u203a', previous: '\u2039' }}
    }}
  }});

  document.querySelector('#variantTable tbody').addEventListener('click', function(e) {{
    const td = e.target.closest('.expand-cell');
    if (!td) return;
    const tr  = td.closest('tr');
    const row = table.row(tr);
    if (row.child.isShown()) {{
      row.child.hide();
      td.innerHTML = '&#9654;';
      tr.classList.remove('shown');
    }} else {{
      row.child(td.dataset.child).show();
      td.innerHTML = '&#9660;';
      tr.classList.add('shown');
    }}
  }});
}})();
</script>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  MATPLOTLIB PLOTS
#
#  IMPORTANT: all plot functions receive df_raw (original MAF column names).
#  This decouples plot generation from the display column selection completely,
#  so plots are always generated regardless of online/offline/plugin flags.
# ══════════════════════════════════════════════════════════════════════════════
def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight",
                facecolor=fig.get_facecolor(), dpi=140)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()


def _apply_dark_style(ax, fig):
    fig.patch.set_facecolor(THEME["surface"])
    ax.set_facecolor(THEME["bg"])
    ax.tick_params(colors=THEME["muted"], labelsize=8)
    ax.xaxis.label.set_color(THEME["muted"])
    ax.yaxis.label.set_color(THEME["muted"])
    ax.title.set_color(THEME["text"])
    for spine in ax.spines.values():
        spine.set_edgecolor(THEME["border2"])
        spine.set_linewidth(0.6)


def plot_vc_distribution(df_raw: pd.DataFrame) -> str:
    """Horizontal bar chart using Consequence (original MAF name)."""
    col = "Consequence"
    if col not in df_raw.columns:
        print(f"  WARNING: Plot skipped, '{col}' not in MAF", file=sys.stderr)
        return ""
    counts = (
        df_raw[col]
        .replace("", np.nan)
        .dropna()
        .str.split("&")
        .str[0]
        .value_counts()
    )
    if counts.empty:
        return ""

    fig, ax = plt.subplots(figsize=(8, max(3, len(counts) * 0.42)))
    colours = [VC_COLOURS.get(c, THEME["accent"]) for c in counts.index]
    bars = ax.barh(counts.index, counts.values, color=colours, height=0.65, edgecolor="none")
    mx = counts.values.max()
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_width() + mx * 0.01, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", color=THEME["muted"],
                fontsize=7.5, fontfamily="monospace")
    ax.set_xlabel("Count", fontsize=8)
    ax.set_title("Variant Classification", fontsize=10, fontweight="600", pad=10)
    ax.invert_yaxis()
    ax.set_yticks(range(len(counts.index)))
    ax.set_yticklabels([l.replace("_", " ") for l in counts.index], fontsize=8)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _apply_dark_style(ax, fig)
    fig.tight_layout(pad=1.2)
    return _fig_to_b64(fig)


def plot_top_genes(df_raw: pd.DataFrame, n: int = 20) -> str:
    """Horizontal bar chart using Hugo_Symbol (original MAF name)."""
    col = "Hugo_Symbol"
    if col not in df_raw.columns:
        print(f"  WARNING: Plot skipped, '{col}' not in MAF", file=sys.stderr)
        return ""
    counts = df_raw[col].replace("", np.nan).dropna().value_counts().head(n)
    if counts.empty:
        return ""

    fig, ax = plt.subplots(figsize=(9, max(3, len(counts) * 0.42)))
    colours = [THEME["ok"] if i < 3 else THEME["accent"] for i in range(len(counts))]
    bars = ax.barh(counts.index, counts.values, color=colours, height=0.65, edgecolor="none")
    mx = counts.values.max()
    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_width() + mx * 0.01, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", ha="left", color=THEME["muted"],
                fontsize=7.5, fontfamily="monospace")
    ax.set_xlabel("Variant count", fontsize=8)
    ax.set_title(f"Top {n} Mutated Genes", fontsize=10, fontweight="600", pad=10)
    ax.invert_yaxis()
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    _apply_dark_style(ax, fig)
    fig.tight_layout(pad=1.2)
    return _fig_to_b64(fig)


def plot_clinvar_pie(df_raw: pd.DataFrame) -> str:
    """Donut chart using CLIN_SIG (original MAF name)."""
    col = "encoded_CLNSIG"
    if col not in df_raw.columns:
        print(f"  WARNING: Plot skipped, '{col}' not in MAF", file=sys.stderr)
        return ""
    sig = df_raw[col].replace("", np.nan).dropna()
    if sig.empty:
        return ""

    counts = sig.value_counts()
    colour_map = {
        "pathogenic":             THEME["fail"],
        "likely_pathogenic":      "#e87a5a",
        "uncertain_significance": THEME["pend"],
        "likely_benign":          "#3a8fad",
        "benign":                 THEME["ok"],
    }
    colours = []
    for idx in counts.index:
        matched = THEME["border2"]
        for k, v in colour_map.items():
            if k in idx.lower():
                matched = v
                break
        colours.append(matched)

    fig, ax = plt.subplots(figsize=(6.5, 5))
    wedges, _, autotexts = ax.pie(
        counts.values, labels=None, colors=colours, autopct="%1.1f%%",
        startangle=90, pctdistance=0.78,
        wedgeprops={"edgecolor": THEME["surface"], "linewidth": 2},
    )
    for at in autotexts:
        at.set_color(THEME["text"])
        at.set_fontsize(7.5)
        at.set_fontfamily("monospace")
    ax.add_patch(plt.Circle((0, 0), 0.55, fc=THEME["surface"]))
    ax.legend(wedges, [l.replace("_", " ") for l in counts.index],
              loc="center left", bbox_to_anchor=(1, 0.5),
              fontsize=8, frameon=False, labelcolor=THEME["muted"])
    ax.set_title("ClinVar Significance", fontsize=10, fontweight="600", pad=10,
                 color=THEME["text"])
    fig.patch.set_facecolor(THEME["surface"])
    ax.set_facecolor(THEME["surface"])
    fig.tight_layout(pad=1)
    return _fig_to_b64(fig)


def plot_acmg_histogram(df_raw: pd.DataFrame) -> str:
    """Histogram using acmg_score (original MAF name)."""
    col = "renovo_adj_acmg_score"
    if col not in df_raw.columns:
        print(f"  WARNING: Plot skipped, '{col}' not in MAF", file=sys.stderr)
        return ""
    vals = pd.to_numeric(df_raw[col], errors="coerce").dropna()
    if vals.empty:
        return ""

    fig, ax = plt.subplots(figsize=(7, 3.8))
    bins = np.linspace(vals.min() - 1, vals.max() + 1, 30)
    _, bin_edges, patches = ax.hist(vals, bins=bins, edgecolor="none", color=THEME["accent"])
    for patch, left in zip(patches, bin_edges[:-1]):
        if   left <= -7: patch.set_facecolor(THEME["ok"])
        elif left <= -1: patch.set_facecolor("#3a8fad")
        elif left <=  5: patch.set_facecolor(THEME["pend"])
        elif left <=  9: patch.set_facecolor("#e87a5a")
        else:            patch.set_facecolor(THEME["fail"])

    y_top = ax.get_ylim()[1]
    for cutoff, label, col_c in [
        (-7, "Benign",   THEME["ok"]),
        (-1, "L.Benign", "#3a8fad"),
        ( 5, "VUS-LP",   THEME["pend"]),
        ( 9, "LP-P",     "#e87a5a"),
    ]:
        ax.axvline(cutoff, color=col_c, lw=0.8, linestyle="--", alpha=0.6)
        ax.text(cutoff + 0.1, y_top * 0.92, label,
                color=col_c, fontsize=6.5, fontfamily="monospace", va="top")

    ax.set_xlabel("ACMG Score", fontsize=8)
    ax.set_ylabel("Count", fontsize=8)
    ax.set_title("Suggested Classification Distribution", fontsize=10,
                 fontweight="600", pad=10)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    _apply_dark_style(ax, fig)
    fig.tight_layout(pad=1.2)
    return _fig_to_b64(fig)


def generate_all_plots(df_raw: pd.DataFrame) -> dict:
    """
    Generate all four analysis plots from the raw MAF DataFrame.

    Receives df_raw (not df_display) so that plots are completely independent
    of the display column selection (online/offline/plugin flags) and always
    use the original MAF column names.
    """
    plots = {}
    print("  Generating variant classification plot...", file=sys.stderr)
    plots["vc"]      = plot_vc_distribution(df_raw)
    print("  Generating top-genes plot...", file=sys.stderr)
    plots["genes"]   = plot_top_genes(df_raw)
    print("  Generating ClinVar plot...", file=sys.stderr)
    plots["clinvar"] = plot_clinvar_pie(df_raw)
    print("  Generating ACMG histogram...", file=sys.stderr)
    plots["acmg"]    = plot_acmg_histogram(df_raw)
    return plots


# ══════════════════════════════════════════════════════════════════════════════
#  SUMMARY STATISTICS  (uses df_raw / original MAF column names)
# ══════════════════════════════════════════════════════════════════════════════
def compute_stats(df_raw: pd.DataFrame) -> dict:
    sample_col = "Tumor_Sample_Barcode"   if "Tumor_Sample_Barcode"   in df_raw.columns else None
    sig_col    = "encoded_CLNSIG" if "encoded_CLNSIG" in df_raw.columns else None

    total_variants = len(df_raw)
    total_samples  = df_raw[sample_col].replace("", np.nan).nunique() if sample_col else 1
    pathogenic     = (
        df_raw[sig_col].str.lower().str.contains("pathogenic", na=False).sum()
        if sig_col else 0
    )
    vus     = (
        df_raw[sig_col].str.lower().str.contains("vus", na=False).sum()
        if sig_col else 0
    )
    return {
        "total_samples":  total_samples,
        "total_variants": total_variants,
        "vus":            int(vus),
        "pathogenic":     int(pathogenic),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  HTML PAGE BUILDER
# ══════════════════════════════════════════════════════════════════════════════
def _plot_card(title: str, icon: str, b64: str) -> str:
    if not b64:
        return ""
    return (
        f'<div class="card">'
        f'<div class="card-header"><span class="card-icon">{icon}</span>'
        f'<h2 class="card-title">{title}</h2></div>'
        f'<div class="plot-container">'
        f'<img src="data:image/png;base64,{b64}" alt="{title}"/>'
        f'</div></div>'
    )


def build_html_page(
    patient_code: str,
    table_html: str,
    stats: dict,
    logo_b64,
    logo_mime,
) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    t   = THEME

    logo_header = (
        f'<img src="data:{logo_mime};base64,{logo_b64}" class="header-logo" alt="MuSA"/>'
        if logo_b64 else ""
    )
    logo_hero = (
        f'<img src="data:{logo_mime};base64,{logo_b64}" class="hero-logo" alt="MuSA"/>'
        if logo_b64 else '<span class="logo-fallback">MuSA</span>'
    )

    stat_items = [
        ("total_variants", "Total Variants",    "total"),
        ("total_samples",  "Samples",           "total"),
        ("vus",            "Clinvar VUS",       "pend"),
        ("pathogenic",     "Clinvar Pathogenic","fail"),
    ]
    stats_html = "".join(
        f'<div class="stat {cls}">'
        f'<span class="stat-num">{stats.get(k, 0):,}</span>'
        f'<span class="stat-label">{label}</span></div>'
        for k, label, cls in stat_items
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>MuSA &middot; Variants Report &middot; {patient_code.upper()}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link href="{t['google_fonts']}" rel="stylesheet"/>
<link rel="stylesheet" href="https://cdn.datatables.net/2.0.7/css/dataTables.dataTables.min.css"/>
<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<script src="https://cdn.datatables.net/2.0.7/js/dataTables.min.js"></script>
<style>
{css_vars(t)}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: var(--bg); color: var(--text);
  font-family: var(--font-body); min-height: 100vh;
  overflow-x: hidden; font-size: 14px; line-height: 1.6;
}}
body::before {{
  content: ""; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image: radial-gradient(circle, var(--border2) 1px, transparent 1px);
  background-size: 24px 24px; opacity: .18;
}}

/* header */
header {{
  position: relative; z-index: 10; border-bottom: 1px solid var(--border);
  padding: 0 2.5rem; display: flex; align-items: center;
  justify-content: space-between; height: 56px;
  background: var(--surface); box-shadow: 0 1px 0 var(--border);
}}
.header-left  {{ display: flex; align-items: center; gap: .75rem; }}
.header-logo  {{ height: 28px; width: auto; display: block; opacity: .9; }}
.header-title {{
  font-size: .75rem; font-weight: 500; color: var(--muted);
  letter-spacing: .06em; text-transform: uppercase;
  border-left: 1px solid var(--border2); padding-left: .75rem;
}}
.header-right {{
  font-family: var(--font-mono); font-size: .68rem; color: var(--muted);
  display: flex; gap: 1.8rem; align-items: center;
}}
.header-right span {{ display: flex; gap: .35rem; align-items: center; }}
.header-right b    {{ color: var(--text); font-weight: 500; }}

/* hero */
.hero {{
  position: relative; z-index: 5; padding: 3rem 2.5rem 2.5rem;
  border-bottom: 1px solid var(--border); overflow: hidden;
  background: linear-gradient(135deg, #141828 0%, var(--bg) 60%);
}}
.hero::after {{
  content: "MuSA"; position: absolute; right: -1rem; bottom: -1.5rem;
  font-family: var(--font-display); font-size: 11rem; font-weight: 700;
  line-height: 1; color: var(--accent); opacity: .04;
  pointer-events: none; letter-spacing: -.04em; user-select: none;
}}
.hero-top {{ display: flex; align-items: center; gap: 2rem; margin-bottom: 1.6rem; }}
.hero-logo     {{ height: 12rem; width: auto; flex-shrink: 0; filter: brightness(1.05); }}
.logo-fallback {{
  font-family: var(--font-display); font-size: 2.4rem; font-weight: 700;
  color: var(--accent); letter-spacing: -.02em; flex-shrink: 0;
}}
.hero h1 {{
  font-family: var(--font-display);
  font-size: clamp(2.5rem, 3vw, 2.6rem);
  font-weight: 600; line-height: 1.2; letter-spacing: -.02em; color: var(--text);
}}
.hero h1 em {{ font-style: italic; font-weight: 300; color: var(--accent); }}
.hero-meta {{
  color: var(--muted); font-size: 1rem; margin-bottom: 2rem;
  font-family: var(--font-mono); letter-spacing: .03em;
  display: flex; gap: 1.5rem; flex-wrap: wrap;
}}
.hero-meta span {{ display: flex; gap: .4rem; align-items: center; }}
.hero-meta b    {{ color: var(--text); font-weight: 500; }}

/* stats grid */
.stats {{
  display: grid; grid-template-columns: repeat(4,1fr);
  gap: 1px; background: var(--border);
  border: 1px solid var(--border); border-radius: var(--radius);
  overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.3);
}}
.stat {{
  background: var(--surface); padding: 1.1rem 1.4rem;
  display: flex; flex-direction: column; gap: .2rem;
}}
.stat-num {{
  font-family: var(--font-display); font-size: 2.4rem; font-weight: 700;
  line-height: 1; letter-spacing: -.03em;
}}
.stat-label {{
  font-family: var(--font-mono); font-size: .62rem;
  text-transform: uppercase; letter-spacing: .12em; color: var(--muted);
}}
.stat.ok    .stat-num {{ color: var(--ok); }}
.stat.fail  .stat-num {{ color: var(--fail); }}
.stat.pend  .stat-num {{ color: var(--pend); }}
.stat.total .stat-num {{ color: var(--text); }}

/* content */
.content {{
  position: relative; z-index: 5; padding: 1.5rem 2.5rem 4rem;
  display: flex; flex-direction: column; gap: 1.5rem;
}}
.card {{
  border: 1px solid var(--border); border-radius: var(--radius);
  background: var(--surface); overflow: hidden;
  animation: slideIn .3s ease both;
}}
@keyframes slideIn {{ from{{opacity:0;transform:translateY(6px)}} to{{opacity:1;transform:translateY(0)}} }}
.card-header {{
  padding: .75rem 1.4rem; display: flex; align-items: center; gap: .75rem;
  border-bottom: 1px solid var(--border); background: var(--surface2);
}}
.card-icon  {{ font-size: 1.1rem; }}
.card-title {{ font-weight: 600; font-size: 1rem; color: var(--text); margin: 0; }}

/* table */
.table-wrap {{ padding: 1rem 1.2rem; overflow-x: auto; }}
#variantTable_wrapper .dt-search input,
#variantTable_wrapper select {{
  background: var(--surface2) !important; color: var(--text) !important;
  border: 1px solid var(--border2) !important; border-radius: 99px !important;
  padding: .28rem 1rem !important; font-family: var(--font-mono) !important;
  font-size: .72rem !important; outline: none !important;
}}
#variantTable_wrapper .dt-search input:focus {{
  border-color: var(--accent) !important; box-shadow: 0 0 0 3px #6c5fff20 !important;
}}
#variantTable_wrapper .dt-search input::placeholder {{ color: var(--muted) !important; }}
table.dataTable {{
  border-collapse: collapse !important; font-family: var(--font-mono);
  font-size: .7rem; width: 100% !important; color: var(--text);
}}
table.dataTable thead th {{
  background: var(--surface2) !important; color: var(--ok) !important;
  border-bottom: 1px solid var(--border2) !important;
  font-size: .62rem; letter-spacing: .08em; text-transform: uppercase;
  padding: .55rem .75rem; white-space: nowrap;
}}
table.dataTable tbody tr {{
  background: var(--surface) !important; border-bottom: 1px solid var(--border) !important;
  transition: background .12s;
}}
table.dataTable tbody tr:hover {{ background: var(--surface2) !important; }}
table.dataTable tbody tr.shown {{ background: var(--surface2) !important; }}
table.dataTable tbody td {{
  padding: .45rem .75rem !important; border-right: 1px solid var(--border) !important;
  vertical-align: middle; white-space: nowrap;
}}
.dt-container .dt-paging .dt-paging-button {{
  background: var(--surface2) !important; color: var(--muted) !important;
  border: 1px solid var(--border) !important; border-radius: 4px !important;
  font-family: var(--font-mono) !important; font-size: .7rem !important; margin: 0 2px !important;
}}
.dt-container .dt-paging .dt-paging-button.current,
.dt-container .dt-paging .dt-paging-button:hover {{
  background: var(--accent) !important; color: #fff !important; border-color: var(--accent) !important;
}}
.dt-container .dt-info  {{ color: var(--muted) !important; font-size: .68rem; font-family: var(--font-mono); }}
.dt-container .dt-length label {{ color: var(--muted) !important; font-size: .68rem; font-family: var(--font-mono); }}
.expand-cell {{
  cursor: pointer; text-align: center; color: var(--accent);
  font-size: .75rem; width: 28px; user-select: none;
}}
.child-table {{ width: 100%; border-collapse: collapse; }}
.child-table td {{ padding: .35rem .8rem; border-bottom: 1px solid var(--border); font-size: .7rem; }}
.det-label {{
  color: var(--muted); font-size: .62rem;
  text-transform: uppercase; letter-spacing: .08em; min-width: 160px;
}}
.det-val {{ color: var(--text); word-break: break-word; white-space: normal; }}

/* badges */
.af-badge {{
  font-family: var(--font-mono); font-size: .6rem;
  padding: .15rem .45rem; border-radius: 4px; white-space: nowrap;
}}
.af-badge.private {{ background: var(--fail-dim); color: var(--fail); border: 1px solid var(--fail-border); }}
.af-badge.common  {{ background: var(--ok-dim);   color: var(--ok);    border: 1px solid var(--ok-border); }}
.af-badge.rare   {{var(--pend-dim); color: var(--pend);  border: 1px solid var(--pend-border); }} 
.acmg-badge {{
  font-family: var(--font-mono); font-size: .6rem;
  padding: .15rem .5rem; border-radius: 4px; white-space: nowrap; font-weight: 600;
}}
.acmg-badge.benign            {{ background: var(--ok-dim);   color: var(--ok);   border: 1px solid var(--ok-border); }}
.acmg-badge.likely-benign     {{ background: #3a8fad1a;       color: #3a8fad;     border: 1px solid #3a8fad55; }}
.acmg-badge.vus               {{ background: var(--pend-dim); color: var(--pend); border: 1px solid var(--pend-border); }}
.acmg-badge.likely-pathogenic {{ background: #e87a5a1a;       color: #e87a5a;     border: 1px solid #e87a5a55; }}
.acmg-badge.pathogenic        {{ background: var(--fail-dim); color: var(--fail); border: 1px solid var(--fail-border); }}

.cv-badge {{
  font-family: var(--font-mono); font-size: .58rem;
  padding: .12rem .42rem; border-radius: 4px; white-space: nowrap;
}}
.cv-pathogenic        {{ background: var(--fail-dim); color: var(--fail); border: 1px solid var(--fail-border); font-weight: 600; }}
.cv-likely-pathogenic {{ background: #e87a5a1a; color: #e87a5a; border: 1px solid #e87a5a55; }}
.cv-benign            {{ background: var(--ok-dim);   color: var(--ok);   border: 1px solid var(--ok-border); }}
.cv-likely-benign     {{ background: #3a8fad1a; color: #3a8fad; border: 1px solid #3a8fad55; }}
.cv-vus               {{ background: var(--pend-dim); color: var(--pend); border: 1px solid var(--pend-border); }}
.cv-notclassified     {{ background: var(--pend-surface2); color: var(--pend); border: 1px solid var(--pend-border); }}
.cv-other             {{ background: var(--surface2); color: var(--muted); border: 1px solid var(--border); }}

.vc-badge {{
  font-family: var(--font-mono); font-size: .6rem; padding: .12rem .42rem;
  border-radius: 4px; border: 1px solid; white-space: nowrap; background: transparent;
}}
.pubmed-link {{
  color: var(--accent); text-decoration: none;
  font-family: var(--font-mono); font-size: .65rem;
}}
.pubmed-link:hover {{ text-decoration: underline; }}
.franklin-link {{
  color: var(--ok); text-decoration: none; font-weight: 600; font-size: .7rem;
}}
.franklin-link:hover {{ text-decoration: underline; }}

/* plot grid */
.plot-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(420px,1fr)); gap: 1.2rem;
}}
.plot-container {{ padding: 1rem 1.2rem; }}
.plot-container img {{ width: 100%; height: auto; display: block; border-radius: 6px; }}

/* footer */
footer {{
  position: relative; z-index: 5; border-top: 1px solid var(--border);
  padding: .9rem 2.5rem; display: flex; justify-content: space-between;
  align-items: center; font-family: var(--font-mono); font-size: .62rem;
  color: var(--muted); background: var(--surface);
}}

@media (max-width: 680px) {{
  .stats {{ grid-template-columns: repeat(2,1fr); }}
  .hero-top {{ flex-direction: column; align-items: flex-start; gap: 1rem; }}
  .hero-logo {{ height: 3rem; }}
  header, .hero, .content, footer {{ padding-left: 1rem; padding-right: 1rem; }}
  .hero::after {{ font-size: 6rem; }}
  .plot-grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>

<header>
  <div class="header-left">
    {logo_header}
    <span class="header-title">Variants Report</span>
  </div>
  <div class="header-right">
    <span>patient <b>{patient_code.upper()}</b></span>
    <span>generated <b>{now}</b></span>
  </div>
</header>

<div class="hero">
  <div class="hero-top">
    {logo_hero}
    <h1>{patient_code.upper()}<br/><em>Variants Report</em></h1>
  </div>
  <div class="hero-meta">
    <span>patient <b>{patient_code.upper()}</b></span>
    <span>reference <b>hg38</b></span>
    <span>{stats['total_variants']:,} variants</span>
  </div>
  <div class="stats">{stats_html}</div>
</div>

<div class="content">
  <div class="card">
    <div class="card-header">
      <span class="card-icon">&#128203;</span>
      <h2 class="card-title">Variants browser</h2>
    </div>
    <div class="table-wrap">{table_html}</div>
  </div>
</div>
<footer>
  <span>MuSA &middot; Multi Source Variant Annotation</span>
  <span>Patient <b>{patient_code.upper()}</b> &middot; {now}</span>
  <span>Made with &#10084; at IRCCS Istituto Ortopedico Rizzoli, Bologna, Italy</span>
</footer>

</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main():
    params = parse_args()
    patient_code    = params["patient_code"]
    use_vep_plugins = params["use_vep_plugins"]
    offline         = params["offline"] or params["skip_genebe"]
    logo_path       = params["logo_path"]

    print("MuSA: Annotate Reporter", file=sys.stderr)
    print(f"  patient        : {patient_code}",    file=sys.stderr)
    print(f"  offline        : {offline}",          file=sys.stderr)
    print(f"  use_vep_plugins: {use_vep_plugins}",  file=sys.stderr)
    print(f"  logo_path      : {logo_path}",        file=sys.stderr)

    logo_b64, logo_mime = load_logo_base64(logo_path)

    print("Loading MAF data...", file=sys.stderr)
    df_raw = load_maf_data(patient_code)

    print("Preparing display data...", file=sys.stderr)
    df_display, main_cols, det_cols = prepare_display_data(
        df_raw, offline, use_vep_plugins
    )

    # Stats and plots both use df_raw (original column names)
    print("Computing statistics...", file=sys.stderr)
    stats = compute_stats(df_raw)

    print("Generating plots...", file=sys.stderr)
    plots = generate_all_plots(df_raw)

    print("Building table...", file=sys.stderr)
    table_html = build_table_html(df_display, main_cols, det_cols)

    print("Assembling HTML...", file=sys.stderr)
    html = build_html_page(
        patient_code=patient_code,
        table_html=table_html,
        stats=stats,
        logo_b64=logo_b64,
        logo_mime=logo_mime,
    )

    out_file = f"{patient_code}_maf_dashboard.html"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK  Report written: {out_file}", file=sys.stderr)

    # lib/ directory expected by Nextflow output tuple
    os.makedirs("lib", exist_ok=True)
    open("lib/.keep", "w").close()


if __name__ == "__main__":
    main()
