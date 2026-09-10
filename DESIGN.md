# Design

The visual system shared by MuSA's two generated documents: the per-patient annotation report
(`bin/build_annotate_report.py`) and the per-data-directory setup report
(`bin/build_setup_report.py`). Both are single self-contained HTML files with **no network
dependency of any kind at read time**.

## Theme

**Light.** The scene decides it: a clinical geneticist at 4pm, fifth hour of a case, lit lab office,
27-inch monitor, cross-checking a shortlist before an MDT meeting. The document is also printed and
forwarded. Dark is for imaging workstations, not for a record that leaves the room.

Single theme, deliberately. These are documents, not an app chrome that should follow the OS.

## Color

Strategy: **Restrained.** Tinted neutrals plus one accent, semantic color reserved for clinical
meaning. This is the direct answer to the previous `#0b0d14` + `#6c5fff` scheme, which read as
gaming dashboard rather than diagnostics.

Neutrals are cool-tinted toward the accent's hue, never warm. Warm near-whites (cream, sand, paper)
are explicitly excluded.

The accent is MuSA's own mark colour, sampled from `assets/MuSA_logo_light.png` (#362276), not an
invented one. It is a deep, sober indigo and should not be confused with the `#6c5fff` neon violet
of the previous dark theme, which is what the anti-reference rules out.

```
--bg              oklch(0.985 0.002 250)   page ground
--surface         oklch(1     0     0  )   table and panel faces
--surface-sunken  oklch(0.966 0.004 250)   toolbars, table head, detail rows
--border          oklch(0.905 0.006 250)   hairlines
--border-strong   oklch(0.82  0.008 250)   dividers that must read
--ink             oklch(0.26  0.012 255)   body text          (13.9:1 on --bg)
--ink-muted       oklch(0.47  0.013 255)   labels, secondary  ( 5.9:1 on --bg)
--accent          oklch(0.395 0.130 292)   deep indigo, taken from the logo ink #362276
```

Accent carries interactive state only: focus rings, links, the active view, sort direction. Never
decoration, and never a fill behind large areas — with exactly one exception, below.

### The inked band

The annotation report's header band is the one large field of colour in either document: a
near-black in the brand's own hue, carrying the case's headline figure and both classifiers.

```
--band        oklch(0.255 0.035 292)   near-black, brand hue
--band-ink    oklch(0.970 0.005 292)   text on the band
--band-muted  oklch(0.760 0.020 292)   secondary text on the band
```

It exists because a white masthead over a white working page gave the document no identity at all,
and because the two classifiers read better as figures than as a row of labelled numbers. The
significance ramp is relit for that ground rather than reused (`--sig-*-lift`, the same hues at
L 0.78–0.86); the dark ramp on light or the light ramp on dark both fail AA, and the audit checks
the band in place.

One band, not a system of them. A second inked area anywhere in either document is drift.

### Clinical semantics

Five-step significance ramp. Deliberately **not** a red-to-green axis: benign resolves to teal and
likely-benign to blue, so the pathogenic/benign distinction survives deuteranopia and protanopia.

```
--sig-p     oklch(0.50 0.17  25)   Pathogenic
--sig-lp    oklch(0.58 0.14  45)   Likely pathogenic
--sig-vus   oklch(0.58 0.11  75)   Uncertain significance
--sig-lb    oklch(0.55 0.09 230)   Likely benign
--sig-b     oklch(0.50 0.08 165)   Benign
--sig-nc    oklch(0.60 0.008 255)  Not classified
```

Setup report states reuse the same ramp: VERIFIED = `--sig-b`, MISMATCH = `--sig-p`,
PENDING = `--sig-vus`.

**Color is never the only signal.** Every significance chip carries its abbreviation (`P`, `LP`,
`VUS`, `LB`, `B`, `NC`); every setup state carries its word. A reader who sees no color at all still
gets the full meaning.

**One vocabulary for both classifiers.** ClinVar and ReNOVo appear side by side on every row, so
they are read on the same five-step scale. ReNOVo reports direction and confidence as one string,
and folds onto that scale with confidence carrying the strength of the call — a low-confidence call
in either direction is what "uncertain" means:

| RENOVO_Class | chip |
|---|---|
| HP Pathogenic | `P` |
| IP Pathogenic | `LP` |
| LP Pathogenic | `VUS` |
| LP Benign | `VUS` |
| IP Benign | `LB` |
| HP Benign | `B` |

The mapping lives once, in `RENOVO_SCALE` in `bin/musa_report_style.py`, mirrored in the page's JS
because the table renders client-side. They must not drift.

The cost of one vocabulary is that a bare pair of chips reading `P  LB` no longer says which
classifier said which, so wherever the two sit together outside a headed table column they are
named (`.chip-src`).

ClinVar's *conflicting classifications* shares the `VUS` chip, because five steps is the scale, but
it is not the same finding as an uncertain classification: it means submitters disagree. Anything
that needs to tell them apart calls `is_conflicting()`. It sorts above VUS, and it joins the flagged
findings group rather than the uncertain one.

Measured under simulated deuteranopia and protanopia, the ramp separates where it matters and
converges where it does not:

| pair | normal | deuteranopia | protanopia |
|---|---|---|---|
| P vs B (the decision that matters) | wide | wide | wide |
| LP vs VUS | 42 | **19** | 28 |
| LB vs NC | wide | **37** | 31 |

So the pathogenic/benign axis survives, while the two *within-group* pairs (both-concerning, and
both-unconcerning) become hard to tell apart on colour alone. That is an acceptable outcome only
because the letter code is always present and is the primary carrier. Do not remove the codes to
tidy the table, and do not add a seventh colour to the ramp; there is no room left in the gamut for
one that stays distinct under both simulations while holding AA contrast on white.

Contrast is verified numerically, not by eye. Chromium reports computed colours in the authored
space, so `getComputedStyle().color` returns `oklch(...)` and neither a regex nor a canvas context
will convert it: an audit must do the OKLCH to linear-sRGB conversion itself or it will silently
compare garbage. Both documents currently pass WCAG 2.2 AA on every text node.

## Typography

Three system stacks, no webfonts. A downloaded font is a network dependency or a multi-hundred-KB
data URI; neither is acceptable here, and system stacks render natively on the lab desktops these
open on.

```
--font-serif  ui-serif, "Iowan Old Style", Palatino, "Book Antiqua", Georgia, serif
--font-sans   ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial
--font-mono   ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace
```

- **Serif** carries document identity only: the report title and section headings. It is what makes
  the page read as a record rather than a dashboard, and it is the contrast axis against the sans.
- **Sans** carries all UI: controls, labels, buttons, prose.
- **Mono** carries all genomic and numeric data: coordinates, HGVS, allele frequencies, checksums,
  versions. Always with `font-variant-numeric: tabular-nums` so digits align in columns.

Fixed rem scale, ratio ~1.2. No fluid `clamp()` headings: these are read at a consistent desk
distance, and a heading that reflows with the window looks worse, not better.

The root is set to **110%**, so the whole scale moves together rather than each size being nudged by
hand. These are read for hours at desk distance on lab monitors; the browser default was tight.

## Layout

The setup report is a **fixed header over one scrolling working surface**: masthead → integrity
summary → provenance ledger, one row per resource. No card grid; the ledger *is* the page.

The annotation report is **two pages in one file**. It opens on findings and the variant table is a
step away, not the bottom of the same scroll. A 68,000-row surface presented first is a search
problem handed to a reader who came for an answer.

**Page one, findings.** Masthead → inked band → findings on the left, the selected variant's
evidence in a panel on the right.

The masthead is the square mark plus a wordmark set in type, with the version taken from
`workflow.manifest.version` at run time, and nothing else. The banner asset had "v1.0" drawn into
the pixels, which was already wrong for the next tag and could only be corrected by re-drawing art.

The band has two halves, divided by a rule: **the case on the left, what was found in it on the
right.** The case identity used to sit in the masthead, which is the wrong place for it — the
masthead identifies the software, the band identifies the patient. Left carries the patient, the
assembly, when the report was generated, whether MuSA ran offline, and the case's **HPO terms**,
each linking out to `hpo.jax.org`. Those terms are the reason the case is being read at all and
were previously nowhere in the document; offline MuSA has the identifiers but not their names, so
the identifier is the link text. Right carries the review-set figure and the two spectra.

The band carries the review-set count as a single large figure, and each classifier as a
proportional spectrum with a legend beneath it. Everything in the band is counted **over the review
set**, the same denominator as the findings below. It used to count every annotated variant, which
put "P 3" directly above "ClinVar flagged 2": two true numbers and a contradiction on screen.

There are no summary charts. A consequence-profile bar chart and a population-frequency bar chart
were tried and removed: neither changed what a reader did next, which is the only test a figure in
a clinical document has to pass.

The findings are a bullet list of the reasons a variant is worth a second look, counted from the
actual data. Each block names its count, previews up to six of its variants, and its header is the
control that opens the table filtered to exactly that block. One definition (`GROUPS` in
`build_annotate_report.py`) drives the count, the preview and the filter, so they cannot disagree.

| block | why |
|---|---|
| ClinVar flagged | pathogenic, likely pathogenic or conflicting |
| Loss of function in an established disease gene | `IMPACT` HIGH in a gene ClinGen rates definitive or strong |
| Homozygous or hemizygous | `AC == AN`: no wild-type allele was called |
| ClinVar VUS, ReNOVo pathogenic | uncertain to ClinVar, called by MuSA |
| Not classified by ClinVar | ReNOVo calls it, ClinVar has never seen it |
| Calls contradict | the two point in opposite directions |

The middle two come from the variant and the gene rather than from either classifier, which is the
point of them: they surface candidates no classifier has flagged yet. On patient 6534 the
loss-of-function block opens with a homozygous frameshift in *PEX5*, absent from gnomAD, in a gene
ClinGen ties to a recessive peroxisome biogenesis disorder — and ClinVar calls it VUS while ReNOVo
calls it benign, so no classifier-driven block would have shown it.

Every preview row carries the **disease**, from ClinVar's `CLNDN`. "CPT2 p.Ser113Leu P" does not say
what the variant is pathogenic *for*, which is the first thing a reader needs in order to decide
whether it bears on the case in front of them. Under it sits the triage strip — impact, zygosity,
absence from gnomAD, the gene's established relationship and inheritance, the ClinVar star rating —
so a reviewer can pick candidates off the list without opening anything.

Previews prefer distinct genes: a group of 175 can otherwise open with six indels from one 60 bp
window and say nothing about the other 169.

**Page two, the table.** Sticky control bar → virtual table → docked evidence panel. The bar carries
the way back, the review-set/all-variants switch, and, when the table was opened from a findings
block, a named filter chip that says which block and carries the control that clears it.

The table sorts on clinical priority by default: ClinVar rank, then a ReNOVo pathogenic call, then
rarity. Opening the table puts the pathogenic calls on the first screen.

## The evidence panel

Full evidence for one variant is a single block of markup with two homes: docked beside the findings
on page one, docked beside the table on page two. **Never over them.** A reader triaging candidates
has to see the list and one variant at the same time, and a dialog covers exactly the thing being
compared against. It is also not an expanding row: expansion gives rows variable height, which makes
virtual scrolling fragile at 68,000 rows, and a fixed panel stays put while arrow keys walk the list.

The panel opens with the **assessment**: the evidence already read, one line per fact, the decisive
ones marked. Before it, the panel was a flat dump of every column in `DETAIL_COLUMNS`, which left
the reader holding eight fields in their head and doing the reasoning themselves.

```
▸ ClinVar and ReNOVo both call this pathogenic.
▸ High-impact change (frameshift variant), predicted to disrupt the protein.
• Called heterozygous.
▸ NEB has a definitive gene-disease relationship with nemaline myopathy 2 (autosomal recessive).
• The gene is moderately constrained against loss of function (LOEUF 0.597).
```

Each line is a claim a clinician may act on, so the wording is held to what the number supports.
LOEUF reads in three bands (`< 0.35` strongly constrained, `< 1.0` moderately, above that not);
calling 0.6 "tolerant of loss of function" would be wrong, not merely loose.

Then the identifiers, as links. Every accession in the MAF is a dead end unless it is one, and the
fields carrying them are inconsistent enough that a single column will not do: `clinvar_OMIM_id` is
populated on 1,781 of 73,008 rows, `CLNDISDB` carries OMIM numbers on 18,113, and `MIM_disease`
embeds more as `[MIM:615413]Disease name`. All three are read, plus MONDO, Orphanet, dbSNP, COSMIC,
PubMed, gnomAD and ClinVar itself — by variation ID where present, by allele ID where not
(`clinvar_id` is populated on 3,372 rows against `ALLELEID`'s 20,321). Beyond ten, they fold away.

Then the fields, grouped in the order the decision is made: the change, the population, the disease,
the gene's constraint, the prediction, the call quality, the model organisms. Absent fields are
omitted rather than printed as "not reported"; `bioinfo_params` is parsed into a small table, since
the two things anyone asks of it — the zygosity, and whether there were enough reads to believe the
call — were buried mid-way through a 150-character run-on.

## Data rendering

The variant payload is embedded as **columnar, dictionary-encoded JSON** and rendered through a
virtual scroller: only the visible window exists in the DOM.

This is a correctness property, not an optimisation. The previous implementation emitted one `<tr>`
per variant plus a full HTML detail table inside a `data-child` attribute on every row: 683,381
elements and a 167 MB file for a single patient. Columnar encoding brings the same data to ~26 MB,
and virtual rendering keeps the DOM at a few hundred nodes regardless of variant count.

## Motion

Near none, by intent. These are read for hours; nothing may move while someone is reading.

Permitted: 120-180 ms state transitions on hover, focus and row expansion. Nothing else. No load
sequences, no scroll reveals, no staggered entrances. All of it inside
`@media (prefers-reduced-motion: reduce)` guards.

## Accessibility

WCAG 2.2 AA contrast as a floor, verified numerically rather than by eye. Color never the sole
carrier of meaning. Full keyboard operability of the table, its sort controls and its row expansion.
Real table semantics (`<table>`, `<th scope>`, `aria-sort`) so the document is navigable by screen
reader.
