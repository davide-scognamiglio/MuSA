# Vendored typefaces

**Poppins**, latin subset, weights 400 / 500 / 600 / 700, as `woff2`.
Source: Google Fonts (`fonts.gstatic.com`), Poppins v24. Licence: SIL Open Font
Licence 1.1, `OFL.txt` in this directory.

These are vendored rather than linked because MuSA's reports are single self-contained
HTML files that must render with **no network access of any kind at read time**. The
report generator base64-embeds them into each document's `<style>` block
(`load_fonts()` in `bin/musa_report_style.py`), which costs about 42 KB per report.

The latin subset is deliberate: the full family is roughly ten times the size and MuSA's
reports carry gene symbols, HGVS strings and English prose.

If this directory is missing, the reports fall back to the system sans stack and stay
correct; they just stop looking like MuSA.
