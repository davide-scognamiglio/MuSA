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
decoration, never a fill behind large areas.

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

## Layout

Both documents are a **fixed header over one scrolling working surface**. No card grids: the table
*is* the page. Cards would add a frame around the only thing anyone came to read.

Annotation report: sticky masthead → counts strip → **findings lede** → **priority findings** →
**overview charts** → sticky control bar → virtual table.
Setup report: masthead → integrity summary → provenance ledger, one row per resource.

The annotation report opens on a conclusion, not on data. The lede is a sentence assembled from
what was actually found ("ReNOVo calls 34 variants pathogenic that ClinVar has never classified"),
then the variants behind that sentence are listed as clickable findings grouped by *why* they are
there, and only then does the table begin. A clinician who reads nothing else should still leave
with the case's headline.

Three charts, all plain HTML and CSS rather than SVG paths or a charting library:

- **ClinVar against ReNOVo** - a counts matrix. This is the figure specific to MuSA: nowhere else
  does the report show where its own classifier and ClinVar disagree, or where MuSA has an opinion
  and ClinVar has none. Off-diagonal cells are marked.
- **Consequence profile** - proportional bars over the review set.
- **Population frequency** - rarity bands, each with its own tone rather than one colour scaled by
  count, which made the commonest band the loudest bar.

The table sorts on clinical priority by default: ClinVar rank, then a ReNOVo pathogenic call, then
rarity. Opening the report puts the pathogenic calls on the first screen.

Full evidence for the selected variant lives in a panel docked to the right of the table, not in a
modal and not in an expanding row. Two reasons: expansion gives rows variable height, which makes
virtual scrolling fragile at 68,000 rows; and during review the panel stays put while arrow keys walk
the list, so the reader compares variants without the page reflowing under them.

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
