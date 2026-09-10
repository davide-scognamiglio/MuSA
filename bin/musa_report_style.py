"""MuSA report design system.

Shared by build_annotate_report.py and build_setup_report.py so the two documents cannot drift
apart. See DESIGN.md at the repository root for the reasoning behind every value here.

Kept as a sibling module in bin/: Nextflow puts the whole bin/ directory on PATH, and a script
executed from PATH has its own directory on sys.path, so `import musa_report_style` resolves.

No webfonts, no CDN, no network of any kind. MuSA runs offline by default and these reports are
read on lab desktops that may have no route out at all.
"""

import base64
import os
import re
import sys


# ── typeface ──────────────────────────────────────────────────────────────────
# Poppins, latin subset, base64-embedded. A <link> to a font CDN would break the one
# hard promise these documents make — no network of any kind at read time — so the
# face travels inside the file. Four weights of latin-subset woff2 cost ~42 KB
# base64 against a ~33 MB report, which is nothing; the full family would be ten
# times that and MuSA's reports are gene symbols, HGVS strings and English prose.
FONT_WEIGHTS = (400, 500, 600, 700)


def load_fonts(assets_dir):
    """Return @font-face rules with the woff2 files inlined, or "" if unavailable.

    A missing fonts directory is not an error: the stack below falls through to the
    system sans and the document stays correct, it just stops looking like MuSA.
    """
    if not assets_dir:
        return ""
    faces = []
    for weight in FONT_WEIGHTS:
        path = os.path.join(assets_dir, "fonts", f"Poppins-{weight}.woff2")
        if not os.path.isfile(path):
            print(f"  WARNING: {path} not found, falling back to the system sans stack",
                  file=sys.stderr)
            return ""
        with open(path, "rb") as fh:
            b64 = base64.b64encode(fh.read()).decode()
        faces.append(
            "@font-face{font-family:Poppins;font-style:normal;font-weight:%d;"
            "font-display:block;src:url(data:font/woff2;base64,%s) format('woff2')}"
            % (weight, b64)
        )
    return "\n".join(faces)

# ── tokens ────────────────────────────────────────────────────────────────────
# Contrast against --bg, measured rather than eyeballed:
#   --ink        13.9:1   --ink-muted   5.9:1   --accent   9.0:1
TOKENS = """
:root {
  color-scheme: light;

  --bg:             oklch(0.985 0.002 250);
  --surface:        oklch(1     0     0  );
  --surface-sunken: oklch(0.966 0.004 250);
  --border:         oklch(0.905 0.006 250);
  --border-strong:  oklch(0.820 0.008 250);
  --ink:            oklch(0.260 0.012 255);
  --ink-muted:      oklch(0.470 0.013 255);
  /* MuSA's own mark is inked #362276, a deep indigo. Taking the accent from the
     logo rather than inventing one keeps the document on-brand; it is a long way
     from the #6c5fff neon of the previous dark theme. 9.0:1 on --bg. */
  --accent:         oklch(0.395 0.130 292);
  --accent-weak:    oklch(0.395 0.130 292 / 0.09);
  --accent-ring:    oklch(0.395 0.130 292 / 0.32);

  /* Clinical significance ramp. Deliberately not red-to-green: benign resolves to
     teal and likely-benign to blue, so pathogenic vs benign survives deuteranopia
     and protanopia. Every chip also carries its abbreviation as text. */
  --sig-p:    oklch(0.50 0.17  25);
  --sig-lp:   oklch(0.55 0.14  45);
  --sig-vus:  oklch(0.52 0.11  75);
  --sig-lb:   oklch(0.52 0.09 230);
  --sig-b:    oklch(0.47 0.08 165);
  --sig-nc:   oklch(0.55 0.008 255);

  /* The same ramp lifted for the inked band, where the ground is near-black instead
     of white. Not a second palette: same hues, same order, relit. */
  --band:        oklch(0.255 0.035 292);
  --band-ink:    oklch(0.970 0.005 292);
  --band-muted:  oklch(0.760 0.020 292);
  --band-line:   oklch(0.380 0.035 292);
  --band-link:   oklch(0.830 0.080 250);
  --sig-p-lift:   oklch(0.78 0.15  25);
  --sig-lp-lift:  oklch(0.82 0.13  45);
  --sig-vus-lift: oklch(0.86 0.12  90);
  --sig-lb-lift:  oklch(0.80 0.10 230);
  --sig-b-lift:   oklch(0.83 0.11 165);
  --sig-nc-lift:  oklch(0.72 0.012 255);

  /* One family carries the whole document, with weight and tracking doing the work
     the old serif/sans split did. The serif role is gone: it resolved to Times on
     most Linux desktops, which read as a memo from 1998 rather than as a clinical
     record. Data stays mono, always. */
  --font-display: Poppins, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  --font-sans:    Poppins, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  --font-mono:    ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, "Liberation Mono", monospace;

  --step--1: 0.75rem;
  --step-0:  0.8125rem;
  --step-1:  0.9375rem;
  --step-2:  1.125rem;
  --step-3:  1.375rem;
  --step-4:  1.75rem;
  --step-5:  2.25rem;
  --step-6:  3rem;

  --radius: 5px;

  --z-sticky:  10;
  --z-panel:   20;
  --z-toast:   30;
  --z-modal:   40;
}
"""

# ── base ──────────────────────────────────────────────────────────────────────
BASE_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* These are read for hours at desk distance on lab monitors, so the whole rem scale
   is set 10% up from browser default rather than each size being nudged by hand. */
html { -webkit-text-size-adjust: 100%; font-size: 110%; }

body {
  background: var(--bg);
  color: var(--ink);
  font-family: var(--font-sans);
  font-size: var(--step-0);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 2px; }
a:hover { text-decoration-thickness: 2px; }

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 3px;
}

.mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }

/* Visible to screen readers only. Used to give colour-coded chips a spoken
   equivalent and to label controls that read as icons. */
.sr-only {
  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;
}

/* ── masthead ─────────────────────────────────────────────────────────────── */
.masthead {
  position: sticky; top: 0; z-index: var(--z-sticky);
  display: flex; align-items: center; justify-content: space-between;
  gap: 1.5rem;
  padding: 0.6rem 1.5rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}
.masthead-id { display: flex; align-items: center; gap: 0.75rem; min-width: 0; }
/* The mark is the image; the wordmark and version are set in type. The banner asset
   carried its own baked-in "v1.0", which goes stale the moment the pipeline is
   tagged again, and no image height made its strapline legible. */
.masthead-mark { height: 40px; width: 40px; display: block; }
.masthead-wordmark {
  display: flex; align-items: baseline; gap: 0.4rem;
  font-family: var(--font-display); font-size: var(--step-3); font-weight: 600;
  letter-spacing: -0.015em; line-height: 1;
}
.masthead-version {
  font-family: var(--font-mono); font-size: var(--step--1); font-weight: 400;
  color: var(--ink-muted); letter-spacing: 0;
}
.masthead-doc {
  font-size: var(--step--1); color: var(--ink-muted);
  padding-left: 0.875rem; border-left: 1px solid var(--border-strong);
}
.masthead-meta {
  display: flex; gap: 1.25rem; flex-wrap: wrap;
  font-family: var(--font-mono); font-size: var(--step--1);
  color: var(--ink-muted); font-variant-numeric: tabular-nums;
}
.masthead-meta b { color: var(--ink); font-weight: 600; }

/* ── page frame ───────────────────────────────────────────────────────────── */
.wrap { padding: 1.5rem; max-width: 1800px; margin-inline: auto; }

h1.doc-title {
  font-family: var(--font-display); font-weight: 600;
  font-size: var(--step-4); letter-spacing: -0.015em;
  text-wrap: balance; margin-bottom: 0.25rem;
}
.doc-sub { color: var(--ink-muted); font-size: var(--step-1); text-wrap: pretty; }

h2.section-title {
  font-family: var(--font-display); font-weight: 600;
  font-size: var(--step-2); letter-spacing: -0.01em;
  margin-bottom: 0.75rem;
}

/* ── significance chips ───────────────────────────────────────────────────── */
/* The abbreviation is the signal; colour is reinforcement. Removing all colour
   must leave the chip fully readable, which is why the code is always present. */
.chip {
  display: inline-flex; align-items: baseline; gap: 0.3rem;
  font-family: var(--font-mono); font-size: var(--step--1); line-height: 1.4;
  padding: 0.05rem 0.4rem;
  border: 1px solid currentColor; border-radius: 3px;
  white-space: nowrap;
}
.chip b { font-weight: 700; letter-spacing: 0.02em; }
.chip .chip-note { font-weight: 400; opacity: 0.75; }
/* Both classifiers now report on the same five-step scale, which is the point, but
   it means a bare pair of chips reading "P  LB" no longer says which said which.
   Anywhere the two appear side by side outside a headed table column, they are
   named. */
.chip .chip-src {
  font-family: var(--font-sans); font-weight: 400;
  color: var(--ink-muted); margin-right: 0.1rem;
}

.chip.sig-p   { color: var(--sig-p);   background: color-mix(in oklab, var(--sig-p)   8%, transparent); }
.chip.sig-lp  { color: var(--sig-lp);  background: color-mix(in oklab, var(--sig-lp)  8%, transparent); }
.chip.sig-vus { color: var(--sig-vus); background: color-mix(in oklab, var(--sig-vus) 8%, transparent); }
.chip.sig-lb  { color: var(--sig-lb);  background: color-mix(in oklab, var(--sig-lb)  8%, transparent); }
.chip.sig-b   { color: var(--sig-b);   background: color-mix(in oklab, var(--sig-b)   8%, transparent); }
.chip.sig-nc  { color: var(--sig-nc);  background: transparent; border-style: dashed; }

/* ── buttons and controls ─────────────────────────────────────────────────── */
.btn {
  font: inherit; font-size: var(--step--1);
  padding: 0.3rem 0.7rem;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--border-strong); border-radius: var(--radius);
  cursor: pointer;
  transition: background 140ms ease, border-color 140ms ease;
}
.btn:hover { background: var(--surface-sunken); }
.btn[aria-pressed="true"] {
  background: var(--accent-weak);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
}

.field {
  font: inherit; font-size: var(--step--1);
  padding: 0.3rem 0.6rem;
  background: var(--surface); color: var(--ink);
  border: 1px solid var(--border-strong); border-radius: var(--radius);
}
.field::placeholder { color: var(--ink-muted); }

/* ── footer ───────────────────────────────────────────────────────────────── */
.doc-footer {
  border-top: 1px solid var(--border);
  padding: 1rem 1.5rem;
  display: flex; flex-wrap: wrap; gap: 0.5rem 1.5rem;
  justify-content: space-between;
  font-size: var(--step--1); color: var(--ink-muted);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}

@media print {
  .masthead { position: static; }
  .no-print { display: none !important; }
  body { background: #fff; }
}
"""


# ── significance mapping ──────────────────────────────────────────────────────
# One place that decides how a raw MAF value becomes (css_class, code, note).
# Both reports and the review-set filter read from here, so a label can never
# disagree with the colour it is shown in.

def is_conflicting(value):
    """ClinVar's 'conflicting classifications of pathogenicity'.

    It shares the VUS chip, because the five-step scale is what both classifiers are
    read on, but it is not the same finding as an uncertain classification: it means
    submitters disagree. Anything that needs to tell them apart asks here.
    """
    return "conflict" in (value or "").strip().lower()


def clinvar_chip(value):
    """Map an encoded_CLNSIG value to (css_class, code, spoken_label)."""
    v = (value or "").strip().lower()
    if not v or v in (".", "nan", "none"):
        return ("sig-nc", "NC", "not classified")
    if "conflict" in v:
        return ("sig-vus", "VUS", "conflicting interpretations")
    if "likely" in v and "patho" in v:
        return ("sig-lp", "LP", "likely pathogenic")
    if "likely" in v and "benign" in v:
        return ("sig-lb", "LB", "likely benign")
    if "patho" in v:
        return ("sig-p", "P", "pathogenic")
    if "benign" in v:
        return ("sig-b", "B", "benign")
    if "vus" in v or "uncertain" in v:
        return ("sig-vus", "VUS", "uncertain significance")
    if "not classified" in v:
        return ("sig-nc", "NC", "not classified")
    return ("sig-nc", value, value)


# ReNOVo reports confidence and direction in one string: "<HP|IP|LP> <Pathogenic|Benign>",
# where the prefix is high / intermediate / low prediction confidence.
#
# Both classifiers are shown side by side on every row, so they must speak the same
# language: a reader comparing a "P" against a "PATH" is doing translation work in
# their head. ReNOVo's six classes therefore fold onto the same five-step ACMG scale
# ClinVar uses, with confidence carrying the strength of the call: a low-confidence
# call in either direction is exactly what "uncertain significance" means.
RENOVO_SCALE = {
    "HP Pathogenic": ("sig-p",   "P",   "pathogenic, high confidence"),
    "IP Pathogenic": ("sig-lp",  "LP",  "pathogenic, intermediate confidence"),
    "LP Pathogenic": ("sig-vus", "VUS", "pathogenic, low confidence"),
    "LP Benign":     ("sig-vus", "VUS", "benign, low confidence"),
    "IP Benign":     ("sig-lb",  "LB",  "benign, intermediate confidence"),
    "HP Benign":     ("sig-b",   "B",   "benign, high confidence"),
}

_RENOVO_LOOKUP = {k.lower(): v for k, v in RENOVO_SCALE.items()}

# The five-step scale, strongest first. Both chip readers order their legends by it.
SIG_SCALE = ["P", "LP", "VUS", "LB", "B"]


def renovo_chip(value):
    """Map a RENOVO_Class value to (css_class, code, spoken_label)."""
    v = " ".join((value or "").split())
    if not v or v in (".", "nan", "None"):
        return ("sig-nc", "NC", "no ReNOVo call")
    hit = _RENOVO_LOOKUP.get(v.lower())
    if hit:
        cls, code, note = hit
        return (cls, code, f"ReNOVo {note}")
    return ("sig-nc", v, v)


def af_band(value):
    """Map MAX_AF to (css_class, label, spoken_label). Absent means never observed."""
    v = (value or "").strip()
    if not v or v in (".", "nan", "None"):
        return ("sig-p", "not observed", "not observed in population databases")
    try:
        f = float(v)
    except ValueError:
        return ("sig-nc", v, v)
    if f < 1e-4:
        return ("sig-p", f"{f:.2e}", "ultra-rare")
    if f < 0.01:
        return ("sig-lp", f"{f:.4f}".rstrip("0"), "rare")
    if f < 0.05:
        return ("sig-vus", f"{f:.3f}", "low frequency")
    return ("sig-b", f"{f:.3f}", "common")


# Consequences that change protein sequence or splicing. Used by the review-set
# filter; VEP can emit several per variant, '&'-joined.
PROTEIN_AFFECTING = {
    "missense_variant", "stop_gained", "stop_lost", "start_lost",
    "frameshift_variant", "inframe_deletion", "inframe_insertion",
    "protein_altering_variant", "splice_acceptor_variant",
    "splice_donor_variant", "splice_region_variant",
    "splice_donor_5th_base_variant", "splice_donor_region_variant",
    "splice_polypyrimidine_tract_variant", "transcript_ablation",
    "transcript_amplification", "incomplete_terminal_codon_variant",
}


def split_consequences(consequence):
    """VEP emits several consequences per variant. MuSA's MAF joins them with ',',
    while VEP's own VCF output uses '&'. Split on both: matching only '&' silently
    dropped every multi-consequence variant from the review set."""
    if not consequence:
        return []
    return [c.strip() for c in re.split(r"[,&]", str(consequence)) if c.strip()]


def is_protein_affecting(consequence):
    return any(c in PROTEIN_AFFECTING for c in split_consequences(consequence))


# ClinVar review status, encoded upstream by bin/encode_clinvar.py as a 0-4 gold-star
# rating. A bare "1" in a report means nothing to a reader; the assertion criteria do.
CLINVAR_STARS = {
    "0": "no assertion criteria provided",
    "1": "criteria provided, single submitter",
    "2": "criteria provided, multiple submitters, no conflicts",
    "3": "reviewed by expert panel",
    "4": "practice guideline",
}


def clinvar_stars(value):
    """Return (filled, total, description) or None when not reported."""
    v = (value or "").strip()
    if v not in CLINVAR_STARS:
        return None
    n = int(v)
    return (n, 4, CLINVAR_STARS[v])


# ── masthead ──────────────────────────────────────────────────────────────────

def masthead_id(logo_b64, logo_mime, version, doc_label):
    """The shared masthead identity block for both reports.

    The wordmark is type, not pixels, and the version comes from the pipeline
    manifest at run time. The previous banner asset had "v1.0" drawn into it, which
    was already wrong for the next tag and could only be fixed by re-drawing art.
    """
    mark = (f'<img class="masthead-mark" src="data:{logo_mime};base64,{logo_b64}" alt=""/>'
            if logo_b64 else "")
    v = (version or "").strip().lstrip("vV")
    ver = f'<span class="masthead-version">v{v}</span>' if v and v != "—" else ""
    return (f'<div class="masthead-id">{mark}'
            f'<span class="masthead-wordmark">MuSA{ver}</span>'
            f'<span class="masthead-doc">{doc_label}</span></div>')
