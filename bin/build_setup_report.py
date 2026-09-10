#!/usr/bin/env python3
"""MuSA: reference data provenance report.

Emits one self-contained HTML document per data directory, recording exactly which reference
databases an annotation can be run against: version, source URL, download method, and SHA-256 with
its verification state.

This is the document that makes a result defensible months later, so it is built as a ledger, one
row per resource, rather than a grid of cards. A reviewer asking "what was this run against, and is
it intact?" should have the answer in one screen without expanding anything.

No network dependency at read time. Design tokens are shared with the annotation report via
musa_report_style.py.

Usage: build_setup_report.py <manifest.yaml> [output.html] [logo.png] [pipeline_version]
"""

import base64
import datetime
import html
import os
import sys

import musa_report_style as style


# ── manifest ──────────────────────────────────────────────────────────────────
def parse_manifest(path):
    """Minimal indentation-based reader for the two-level manifest MuSA writes.

    Deliberately not PyYAML: this script has no container of its own and runs on whatever host
    Python Nextflow finds, so it must not depend on anything outside the standard library.
    """
    data, genome, entry = {}, None, None
    with open(path) as fh:
        for line in fh:
            raw = line.rstrip("\n")
            stripped = raw.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(raw) - len(stripped)
            if indent == 0 and stripped.endswith(":"):
                genome = stripped[:-1]
                data[genome] = {}
                entry = None
            elif indent == 2 and stripped.endswith(":") and genome:
                entry = stripped[:-1]
                data[genome][entry] = {}
            elif indent == 4 and ":" in stripped and genome and entry:
                key, _, val = stripped.partition(":")
                data[genome][entry][key.strip()] = _scalar(val)
    return data


def _scalar(raw):
    """Take a YAML scalar, dropping any trailing comment.

    The manifest carries lines like

        expected_sha256: ""   # empty -> trust-on-first-use fills it

    and keeping the comment made that entry's expected hash a sentence, so a resource
    with no pinned checksum was reported as a MISMATCH rather than as unpinned.
    """
    val = raw.strip()
    if val[:1] in ('"', "'"):
        quote = val[0]
        end = val.find(quote, 1)
        return val[1:end] if end > 0 else val[1:]
    return val.split("#", 1)[0].strip()


def status_of(entry):
    computed = entry.get("computed_sha256", "")
    expected = entry.get("expected_sha256", "")
    if not computed:
        return "pending"
    if not expected:
        # Downloaded and hashed, but the manifest carries no reference hash to check it
        # against. Not the same as verified, and saying so matters in a provenance record.
        return "unpinned"
    return "verified" if computed == expected else "mismatch"


STATUS = {
    "verified": ("sig-b",   "Verified",  "checksum matches the manifest"),
    "mismatch": ("sig-p",   "Mismatch",  "checksum does NOT match the manifest"),
    "pending":  ("sig-vus", "Pending",   "not yet downloaded or hashed"),
    "unpinned": ("sig-nc",  "Unpinned",  "hashed, but the manifest pins no expected value"),
}


def load_logo_base64(logo_path):
    if not logo_path or not os.path.isfile(logo_path):
        return None, None
    ext = os.path.splitext(logo_path)[1].lower().lstrip(".")
    mime = {"png": "image/png", "svg": "image/svg+xml",
            "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(ext, "image/png")
    with open(logo_path, "rb") as fh:
        return base64.b64encode(fh.read()).decode(), mime


# ── page CSS ──────────────────────────────────────────────────────────────────
PAGE_CSS = """
.intro { padding: 1.5rem 1.5rem 1rem; max-width: 62ch; }

.integrity {
  display: flex; flex-wrap: wrap; gap: 0 2.5rem;
  padding: 0 1.5rem 1.25rem;
}
.integrity-block { display: flex; flex-direction: column; gap: 0.2rem; }
.integrity-label { font-size: var(--step--1); color: var(--ink-muted); }
.integrity-value {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step-3); font-weight: 600; line-height: 1.1;
}
.integrity-value.is-mismatch { color: var(--sig-p); }
.integrity-value.is-pending  { color: var(--sig-vus); }

/* A single proportional bar reads faster than four numbers when the only question
   is "is this data directory sound?". Segments are labelled, not colour-only. */
.bar {
  display: flex; height: 8px; margin: 0 1.5rem 1.5rem;
  border-radius: 4px; overflow: hidden; background: var(--surface-sunken);
  border: 1px solid var(--border);
}
.bar span { display: block; height: 100%; }
.bar .seg-verified { background: var(--sig-b); }
.bar .seg-mismatch { background: var(--sig-p); }
.bar .seg-pending  { background: var(--sig-vus); }
.bar .seg-unpinned { background: var(--border-strong); }

.controls {
  display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem 0.75rem;
  padding: 0.6rem 1.5rem;
  background: var(--surface-sunken);
  border-block: 1px solid var(--border);
  position: sticky; top: 0; z-index: var(--z-sticky);
}
#search { min-width: 240px; }
.result-count {
  margin-left: auto;
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  font-size: var(--step--1); color: var(--ink-muted);
}

table.ledger { width: 100%; border-collapse: collapse; }
table.ledger thead th {
  position: sticky; top: 41px; z-index: 2;
  background: var(--surface); text-align: left;
  font-size: var(--step--1); font-weight: 600; color: var(--ink-muted);
  padding: 0.5rem 1rem; white-space: nowrap;
  border-bottom: 1px solid var(--border-strong);
}
table.ledger tbody td {
  padding: 0.6rem 1rem; border-bottom: 1px solid var(--border);
  vertical-align: top;
}
table.ledger tbody tr:hover td { background: var(--surface-sunken); }
.res-name { font-weight: 600; }
.res-db {
  display: block; font-family: var(--font-mono);
  font-size: var(--step--1); color: var(--ink-muted);
}
.res-file {
  font-family: var(--font-mono); font-size: var(--step--1);
  word-break: break-all;
}
.res-url { font-size: var(--step--1); word-break: break-all; }
.res-version {
  font-family: var(--font-mono); font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.sha {
  font-family: var(--font-mono); font-size: var(--step--1);
  word-break: break-all; color: var(--ink-muted);
}
.sha-pair { display: grid; gap: 0.15rem; }
.sha-tag {
  font-family: var(--font-sans); font-size: var(--step--1);
  color: var(--ink-muted); margin-right: 0.3rem;
}
.sha.bad { color: var(--sig-p); }
.sha-absent { font-style: italic; color: var(--ink-muted); font-size: var(--step--1); }

.empty {
  padding: 2.5rem 1.5rem; text-align: center; color: var(--ink-muted);
}
"""

PAGE_JS = r"""
(function () {
  "use strict";
  var rows = Array.prototype.slice.call(document.querySelectorAll("tbody tr[data-status]"));
  var search = document.getElementById("search");
  var count = document.getElementById("resultCount");
  var empty = document.getElementById("empty");
  var filter = "all";

  function apply() {
    var q = search.value.trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (tr) {
      var okStatus = filter === "all" || tr.dataset.status === filter;
      var okText = !q || tr.textContent.toLowerCase().indexOf(q) >= 0;
      var show = okStatus && okText;
      tr.hidden = !show;
      if (show) shown++;
    });
    count.textContent = shown + (shown === 1 ? " resource" : " resources");
    empty.hidden = shown > 0;
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-filter]"), function (btn) {
    btn.addEventListener("click", function () {
      filter = btn.dataset.filter;
      Array.prototype.forEach.call(document.querySelectorAll("[data-filter]"), function (b) {
        b.setAttribute("aria-pressed", String(b === btn));
      });
      apply();
    });
  });
  search.addEventListener("input", apply);
  apply();
})();
"""

PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Reference data provenance &middot; MuSA</title>
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
    <span class="masthead-doc">Reference data provenance</span>
  </div>
  <div class="masthead-meta">
    <span>Assembly <b>__GENOME__</b></span>
    <span>Pipeline <b>__VERSION__</b></span>
    <span>Generated <b>__GENERATED__</b></span>
  </div>
</header>

<div class="intro">
  <h1 class="doc-title">Reference data provenance</h1>
  <p class="doc-sub">Every database this data directory holds, with the version and SHA-256 checksum
  it was installed under. Keep this file: it is the record of what any annotation produced here was
  actually run against.</p>
</div>

<section class="integrity" aria-label="Integrity summary">
  <div class="integrity-block">
    <span class="integrity-label">Resources</span>
    <span class="integrity-value">__TOTAL__</span>
  </div>
  <div class="integrity-block">
    <span class="integrity-label">Verified against manifest</span>
    <span class="integrity-value">__VERIFIED__</span>
  </div>
  <div class="integrity-block">
    <span class="integrity-label">Checksum mismatch</span>
    <span class="integrity-value __MISMATCH_CLASS__">__MISMATCH__</span>
  </div>
  <div class="integrity-block">
    <span class="integrity-label">Not yet downloaded</span>
    <span class="integrity-value __PENDING_CLASS__">__PENDING__</span>
  </div>
</section>

<div class="bar" role="img" aria-label="__BAR_LABEL__">__BAR__</div>

<div class="controls no-print">
  <div class="controls-group" role="group" aria-label="Filter by verification state">
    __FILTERS__
  </div>
  <label class="sr-only" for="search">Search resources</label>
  <input class="field" id="search" type="search" placeholder="Resource, file or database"/>
  <span class="result-count" id="resultCount" role="status" aria-live="polite"></span>
</div>

<table class="ledger">
  <thead>
    <tr>
      <th scope="col">State</th>
      <th scope="col">Resource</th>
      <th scope="col">Version</th>
      <th scope="col">File</th>
      <th scope="col">SHA-256</th>
      <th scope="col">Source</th>
    </tr>
  </thead>
  <tbody>__ROWS__</tbody>
</table>
<p class="empty" id="empty" hidden>No resource matches this filter.</p>

<footer class="doc-footer">
  <span>MuSA &middot; multi-source variant annotation</span>
  <span>__GENERATED__</span>
  <span>IRCCS Istituto Ortopedico Rizzoli, Bologna</span>
</footer>

<script>__PAGE_JS__</script>
</body>
</html>
"""


ASSEMBLY_LABELS = {"grch38": "GRCh38", "grch37": "GRCh37", "hg38": "hg38", "hg19": "hg19"}


def _assembly_label(genome):
    return ASSEMBLY_LABELS.get(str(genome).lower(), str(genome))


def _esc(v):
    return html.escape(str(v if v not in (None, "") else "—"))


def build_report(yaml_path, output_path="setup_report.html", logo_path=None,
                 pipeline_version="—"):
    data = parse_manifest(yaml_path)
    if not data:
        raise RuntimeError(f"No entries parsed from manifest: {yaml_path}")
    genome = list(data.keys())[0]
    entries = data[genome]

    counts = {k: 0 for k in STATUS}
    rows_html = []

    for key, entry in entries.items():
        st = status_of(entry)
        counts[st] += 1
        cls, label, note = STATUS[st]

        computed = entry.get("computed_sha256", "")
        expected = entry.get("expected_sha256", "")
        if st == "mismatch":
            sha_html = (
                '<div class="sha-pair">'
                f'<div><span class="sha-tag">expected</span><span class="sha">{_esc(expected)}</span></div>'
                f'<div><span class="sha-tag">computed</span><span class="sha bad">{_esc(computed)}</span></div>'
                "</div>"
            )
        elif st == "pending":
            sha_html = '<span class="sha-absent">not yet computed</span>'
        elif st == "unpinned":
            sha_html = (f'<span class="sha">{_esc(computed)}</span>'
                        '<div class="sha-absent">no expected value in the manifest</div>')
        else:
            sha_html = f'<span class="sha">{_esc(computed)}</span>'

        url = entry.get("url", "")
        source = (f'<a class="res-url" href="{html.escape(url)}" rel="noopener noreferrer">'
                  f'{html.escape(url)}</a>' if url else '<span class="sha-absent">—</span>')

        rows_html.append(
            f'<tr data-status="{st}">'
            f'<td><span class="chip {cls}"><b>{label}</b>'
            f'<span class="sr-only"> {note}</span></span></td>'
            f'<td><span class="res-name">{_esc(key)}</span>'
            f'<span class="res-db">{_esc(entry.get("dbname"))}</span></td>'
            f'<td class="res-version">{_esc(entry.get("version"))}</td>'
            f'<td class="res-file">{_esc(entry.get("out"))}'
            f'<span class="res-db">via {_esc(entry.get("method"))}</span></td>'
            f'<td>{sha_html}</td>'
            f'<td>{source}</td>'
            "</tr>"
        )

    total = len(entries)
    bar = "".join(
        f'<span class="seg-{k}" style="width:{counts[k] / total * 100:.4f}%"></span>'
        for k in ("verified", "unpinned", "pending", "mismatch") if counts[k]
    ) if total else ""
    bar_label = ", ".join(f"{counts[k]} {STATUS[k][1].lower()}" for k in STATUS if counts[k])

    filters = ['<button class="btn" type="button" data-filter="all" aria-pressed="true">'
               f'All {total}</button>']
    for k in ("verified", "mismatch", "pending", "unpinned"):
        if counts[k]:
            filters.append(f'<button class="btn" type="button" data-filter="{k}" '
                           f'aria-pressed="false">{STATUS[k][1]} {counts[k]}</button>')

    b64, mime = load_logo_base64(logo_path)
    logo = (f'<img class="masthead-logo" src="data:{mime};base64,{b64}" alt="MuSA"/>'
            if b64 else '<span class="masthead-wordmark">MuSA</span>')

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    page = (PAGE_HTML
            .replace("__TOKENS__", style.TOKENS)
            .replace("__BASE_CSS__", style.BASE_CSS)
            .replace("__PAGE_CSS__", PAGE_CSS)
            .replace("__PAGE_JS__", PAGE_JS)
            .replace("__ROWS__", "".join(rows_html))
            .replace("__FILTERS__", "".join(filters))
            .replace("__BAR__", bar)
            .replace("__BAR_LABEL__", bar_label or "no resources")
            .replace("__TOTAL__", f"{total:,}")
            .replace("__VERIFIED__", f"{counts['verified']:,}")
            .replace("__MISMATCH__", f"{counts['mismatch']:,}")
            .replace("__MISMATCH_CLASS__", "is-mismatch" if counts["mismatch"] else "")
            .replace("__PENDING__", f"{counts['pending']:,}")
            .replace("__PENDING_CLASS__", "is-pending" if counts["pending"] else "")
            .replace("__GENOME__", html.escape(_assembly_label(genome)))
            .replace("__VERSION__", html.escape(str(pipeline_version)))
            .replace("__GENERATED__", now)
            .replace("__LOGO__", logo))

    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(page)

    print(f"Report written to {output_path}: {total} resources, "
          f"{counts['verified']} verified, {counts['mismatch']} mismatch, "
          f"{counts['pending']} pending, {counts['unpinned']} unpinned")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("Usage: build_setup_report.py <manifest.yaml> [output.html] [logo.png] [version]")
    build_report(
        sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else "setup_report.html",
        sys.argv[3] if len(sys.argv) > 3 else None,
        sys.argv[4] if len(sys.argv) > 4 else "—",
    )
