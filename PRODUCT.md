# Product

## Register

product

## Users

**Primary: the clinical geneticist or variant analyst**, at a lab desktop, on a large monitor, in a
lit room, for hours at a stretch. They are working a case: narrowing tens of thousands of annotated
variants down to the handful worth discussing, then defending that shortlist to colleagues. They
already know genetics; they do not want anything explained to them. What they need is to find the
signal fast, and to be able to say where every number came from.

They open two different documents, for two different jobs:

- **The annotation report** (`<patient>_maf_dashboard.html`), per patient, during review. This is
  the working surface: scan, sort, filter, drill into a variant, follow out to ClinVar / Franklin /
  OMIM / PubMed. Long dwell time. Read repeatedly, on the same case, across days.
- **The setup report** (`setup_report.html`), once per data directory, and then again whenever
  someone asks "what was this annotation actually run against?". This is the provenance surface:
  every reference database with its version, source and SHA-256, marked VERIFIED / MISMATCH /
  PENDING. Short dwell time, high stakes. It is the document that makes a result defensible.

**Secondary: whoever inherits the case.** Reports get attached to records and forwarded. A reader
who has never used MuSA should be able to tell what they are looking at and how far to trust it.

## Product Purpose

MuSA annotates germline variants against many sources at once and ranks them for clinical review.
The reports are where that work becomes usable by a person. Success is narrow and testable:

1. The report opens **instantly** and stays responsive while being sorted and filtered.
2. It works with **no network at all**. MuSA runs offline by default; a report that degrades on an
   air-gapped clinical network is not fit for its setting.
3. A reviewer can go from "here are 68,000 variants" to "here are the ones that matter" without
   leaving the page or writing a script.
4. Every value is **attributable**: which database, which version, which transcript.

## Brand Personality

**Authoritative, clinical, formal.** The register of an instrument readout or a validated assay
report, not of a product marketing page. Confidence is earned by showing the working: versions,
checksums, transcript IDs, review status, and honest gaps. When data is missing the report says so
plainly rather than hiding the field.

Voice: declarative, specific, unhedged. Names things the way a geneticist names them (MANE Select,
ClinVar review status, gnomAD popmax) without a glossary tone. No exclamation, no encouragement, no
persuasion. The reader is a peer.

## Anti-references

- **Not the current dark neon look.** The existing `#0b0d14` near-black with a `#6c5fff`
  indigo-violet accent and Poppins throughout reads as gaming or crypto dashboard, not diagnostics.
  Moving away from it is an explicit goal, not an incidental one.
- **Not a plain bioinformatics dump.** Not an unstyled table, not stock DataTables, not a script's
  stdout with a stylesheet bolted on. The care taken over the pipeline should be visible in its
  output.
- **Not a SaaS analytics dashboard.** No gradient KPI tiles, no hero metrics, no growth-chart
  framing. Clinical output must not borrow the visual language of a metrics product.
- **Not decorative.** Nothing on the page that does not carry information a reviewer will act on.

## Design Principles

1. **Attributable by default.** Every number is traceable to a source and version without the reader
   asking. Provenance is the product, not a footnote.
2. **Absence is information.** A missing value is stated (`.`, "not in ClinVar", "no MANE
   transcript") rather than rendered as blank space. A reviewer must never wonder whether a field is
   empty or broken.
3. **Weight is a correctness property.** A report that takes minutes to open is not slow, it is
   unusable. Interactive performance is a requirement, not a polish item.
4. **Self-contained means self-contained.** No network dependency of any kind at read time. The
   document must render identically on an air-gapped workstation and five years from now.
5. **Density serves scanning, not decoration.** Optimise for the fifth hour of review: stable
   column positions, tabular figures, restrained colour, no motion that interrupts reading.

## Accessibility & Inclusion

Target **WCAG 2.2 AA** contrast throughout: body text at least 4.5:1, large text at least 3:1.

**Colour is never the only signal.** This is a hard rule, not a preference. The report currently
encodes 15 variant consequences, three setup states (VERIFIED / MISMATCH / PENDING), plus ACMG
classes, ClinVar significance and allele-frequency bands entirely in hue. Around 8% of men have
red-green colour vision deficiency, and pathogenic-versus-benign is exactly the red-green axis. Every
colour-coded state must also carry text, shape, or position, and the palette is to be checked against
deuteranopia and protanopia simulation before shipping.

Respect `prefers-reduced-motion`. Given the long-session context, avoid anything that animates while
the reader is reading.
