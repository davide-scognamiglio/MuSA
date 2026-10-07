#!/usr/bin/env python3
"""Build MuSA's static site (GitHub Pages) into a directory.

    python3 docs/site/build.py --out _site

Sources, all in the repository:
  docs/site/index.html        the landing page (hand-written; {{TOKENS}} and <!--MAP--> filled here)
  docs/site/templates/        the shell for every other page
  docs/site/tutorials/*.md    tutorials (front matter: title, summary, order)
  docs/site/static/           CSS, JS, fonts, images (the film is fetched from test-datasets)
  docs/site/example/          the published example report (NA12878, basic mode)
  docs/{usage,output,sources}.md, CHANGELOG.md, assets/pipeline_map.svg

The latest-release section and the releases page come from CHANGELOG.md, so the site is rebuilt
whenever a release lands on main. Needs Python >= 3.9 and `markdown` (pip install markdown).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import urllib.request
from pathlib import Path

import markdown

SITE_URL = "https://davide-scognamiglio.github.io/MuSA/"
REPO_URL = "https://github.com/davide-scognamiglio/MuSA"
CONCEPT_DOI = "10.5281/zenodo.23185068"
# Zenodo DOIs per release. v1.2.0 and earlier predate the Zenodo integration.
VERSION_DOIS = {"v1.4.0": "10.5281/zenodo.23185070", "v1.3.0": "10.5281/zenodo.23185069"}

# The film lives in test-datasets, not here, so pipeline users never download it. Pinned by commit
# and checked by SHA-256, like the database manifest.
FILM = {
    "path": "static/video/musa-1.4.mp4",
    "url": "https://raw.githubusercontent.com/davide-scognamiglio/test-datasets/"
           "b990bc950ed8db85d9047664b53721c5949a30e1/site/musa-1.4.mp4",
    "sha256": "a32290e2c444bccb87703a62a6a3850228cc29881de828748b5050d4424dc7ef",
}

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

DOCS = [  # (slug, source, nav title)
    ("usage", "docs/usage.md", "Usage"),
    ("output", "docs/output.md", "Output"),
    ("sources", "docs/sources.md", "Sources"),
]


# ── Markdown ─────────────────────────────────────────────────────────────────────────────────────
def widen_indents(text: str) -> str:
    """Our Markdown nests lists with 2 spaces (GitHub's renderer accepts it); Python-Markdown needs 4."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        if not fenced and line[:1] == " ":
            k = len(line) - len(line.lstrip(" "))
            line = " " * (2 * k) + line[k:]
        out.append(line)
    return "\n".join(out)


GH_ALERT = re.compile(r"<blockquote>\s*<p>\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*")


def md_to_html(text: str) -> str:
    """Markdown to HTML, with GitHub's `> [!WARNING]` alerts rendered as labelled callouts."""
    return GH_ALERT.sub(lambda m: f'<blockquote class="alert"><p><strong>{m.group(1).title()}.</strong> ', _md(text))


def _md(text: str) -> str:
    text = widen_indents(text)
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
        extension_configs={"toc": {"permalink": "#", "permalink_class": "headerlink", "permalink_title": "Link to this section"}},
    )


def front_matter(text: str) -> tuple[dict, str]:
    meta: dict = {}
    if text.startswith("---\n"):
        head, _, text = text[4:].partition("\n---\n")
        for line in head.splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, text


def rewrite_doc_links(body: str, root: str) -> str:
    """Point docs' relative links at their site pages, and anything else at GitHub."""
    slugs = {Path(src).name: slug for slug, src, _ in DOCS}

    def fix(m: re.Match) -> str:
        url = m.group(2)
        if re.match(r"^(https?:|mailto:|#)", url):
            return m.group(0)
        path, _, frag = url.partition("#")
        frag = f"#{frag}" if frag else ""
        name = Path(path).name
        if name in slugs:
            return f'{m.group(1)}"{root}docs/{slugs[name]}/{frag}"'
        if name == "CHANGELOG.md":
            return f'{m.group(1)}"{root}releases/{frag}"'
        target = (Path("docs") / path).as_posix() if not path.startswith("../") else path[3:]
        return f'{m.group(1)}"{REPO_URL}/blob/main/{target}{frag}"'

    return re.sub(r'(<a href=|<img src=)"([^"]+)"', fix, body)


# ── Page shell ───────────────────────────────────────────────────────────────────────────────────
def nav(root: str, current: str) -> str:
    items = [("docs", "Docs", "docs/usage/"), ("tutorials", "Tutorials", "tutorials/"),
             ("releases", "Releases", "releases/"), ("example", "Example report", "example/")]
    lis = "".join(
        f'<li><a href="{root}{href}"{" aria-current=\"page\"" if key == current else ""}>{label}</a></li>'
        for key, label, href in items
    )
    gh = (f'<li><a class="gh" href="{REPO_URL}">GitHub <span aria-hidden="true">↗</span></a></li>')
    return (
        '<nav class="nav" aria-label="Main"><div class="wrap">'
        f'<a class="brand" href="{root}"><img src="{root}static/img/musa-mark.png" alt="" width="28" height="28">MuSA<span>{{{{REL_SHORT}}}}</span></a>'
        '<button class="menu-btn" type="button" aria-expanded="false">Menu</button>'
        f"<ul>{lis}{gh}</ul></div></nav>"
    )


def footer(root: str) -> str:
    return (
        '<footer><div class="wrap">'
        "<span>MuSA · Multi-Source variant Annotation · IRCCS Istituto Ortopedico Rizzoli, Bologna</span>"
        f'<span><a href="{REPO_URL}/blob/main/LICENSE">CC BY-NC 4.0</a> · '
        f'<a href="https://doi.org/10.1186/s12859-026-06513-0">Paper</a> · '
        f'<a href="https://doi.org/{CONCEPT_DOI}">Zenodo</a> · '
        f'<a href="{REPO_URL}">GitHub</a></span>'
        "<span>Research software for variant review by qualified professionals. Not a certified medical device.</span>"
        "</div></footer>"
    )


def sidebar(root: str, current: str, tutorials: list[dict], releases: list[dict]) -> str:
    def group(title: str, links: list[tuple[str, str, str]]) -> str:
        lis = "".join(
            f'<li><a href="{root}{href}"{" aria-current=\"page\"" if key == current else ""}>{label}</a></li>'
            for key, label, href in links
        )
        return f"<h4>{title}</h4><ul>{lis}</ul>"

    docs = [(f"docs/{s}", t, f"docs/{s}/") for s, _, t in DOCS]
    tuts = [("tutorials", "All tutorials", "tutorials/")] + [(f"tutorials/{t['slug']}", t["title"], f"tutorials/{t['slug']}/") for t in tutorials]
    rels = [("releases", "All releases", "releases/")] + [("", r["version"], f"releases/#{r['anchor']}") for r in releases[:4]]
    return group("Documentation", docs) + group("Tutorials", tuts) + group("Releases", rels)


def render_page(out: Path, rel: str, *, title: str, description: str, content: str, current: str,
                tutorials: list, releases: list, pager: str = "") -> None:
    depth = rel.count("/")
    root = "../" * depth
    page = (HERE / "templates/page.html").read_text()
    page = (page.replace("{{NAV}}", nav(root, current.split("/")[0]))
                .replace("{{FOOTER}}", footer(root))
                .replace("{{SIDEBAR}}", sidebar(root, current, tutorials, releases))
                .replace("{{CONTENT}}", content).replace("{{PAGER}}", pager)
                .replace("{{TITLE}}", html.escape(title)).replace("{{DESCRIPTION}}", html.escape(description))
                .replace("{{CANONICAL}}", SITE_URL + rel.rsplit("index.html", 1)[0])
                .replace("{{SITE_URL}}", SITE_URL).replace("{{ROOT}}", root)
                .replace("{{REL_SHORT}}", releases[0]["version"].lstrip("v") if releases else ""))
    dest = out / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(page)


def pager_html(root: str, prev: tuple | None, nxt: tuple | None) -> str:
    a = f'<a href="{root}{prev[1]}"><small>Previous</small>{prev[0]}</a>' if prev else "<span></span>"
    b = f'<a href="{root}{nxt[1]}" style="text-align:right"><small>Next</small>{nxt[0]}</a>' if nxt else "<span></span>"
    return f'<nav class="pager" aria-label="Pages">{a}{b}</nav>'


# ── Releases from CHANGELOG.md ───────────────────────────────────────────────────────────────────
def parse_changelog() -> list[dict]:
    text = (REPO / "CHANGELOG.md").read_text()
    parts = re.split(r"^## (v\d+\.\d+\.\d+) - (\d{4}-\d{2}-\d{2})\s*$", text, flags=re.M)
    releases = []
    for i in range(1, len(parts), 3):
        version, date, body = parts[i], parts[i + 1], parts[i + 2].strip()
        intro = next((p.strip() for p in body.split("\n\n") if p.strip() and not p.startswith(("#", ">", "-"))), "")
        highlights = []
        for sec in re.split(r"^### ", body, flags=re.M)[1:]:
            name, _, sec_body = sec.partition("\n")
            if "Added" not in name and "Changed" not in name:
                continue
            for m in re.finditer(r"^- (.+(?:\n  .+)*)", sec_body, flags=re.M):
                first = re.sub(r"\s+", " ", m.group(1)).strip()
                first = re.sub(r"\*\*(.+?)\*\*.*", r"\1", first) if first.startswith("**") else first
                highlights.append(first.rstrip(":;."))
        releases.append({"version": version, "date": date, "body": body, "intro": intro,
                         "highlights": highlights, "anchor": version.replace(".", "-")})
    return releases


def releases_page(releases: list[dict]) -> str:
    out = ['<h1>Releases</h1>',
           f'<p>Every release is on <a href="{REPO_URL}/releases">GitHub</a>. Releases from v1.3.0 on are archived on Zenodo; '
           f'cite <a href="https://doi.org/{CONCEPT_DOI}">{CONCEPT_DOI}</a> for all versions, or the version DOI below. '
           'Run a specific release with <code>-r &lt;version&gt;</code>.</p>']
    for r in releases:
        doi = VERSION_DOIS.get(r["version"])
        meta = f'{r["date"]} · <a href="{REPO_URL}/releases/tag/{r["version"]}">GitHub</a>'
        if doi:
            meta += f' · <a href="https://doi.org/{doi}">doi:{doi}</a>'
        body = re.sub(r"^### `?([^`\n]+)`?", r"### \1", r["body"], flags=re.M)
        out.append(f'<h2 id="{r["anchor"]}">{r["version"]}</h2><p style="color:var(--muted)">{meta}</p>')
        # Section ids repeat across releases (Added, Fixed...), so prefix them with the version.
        out.append(re.sub(r'<h3 id="([^"]+)">(.*?)href="#\1"',
                          lambda m: f'<h3 id="{r["anchor"]}-{m.group(1)}">{m.group(2)}href="#{r["anchor"]}-{m.group(1)}"',
                          md_to_html(body)))
    return "\n".join(out)


def fetch_film() -> None:
    """Download the film into docs/site/static (gitignored) unless a verified copy is already there."""
    dest = HERE / FILM["path"]
    if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == FILM["sha256"]:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(FILM["url"], timeout=60) as resp:
        data = resp.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != FILM["sha256"]:
        raise SystemExit(f"Film checksum mismatch: expected {FILM['sha256']}, got {digest}")
    dest.write_bytes(data)


# ── Build ────────────────────────────────────────────────────────────────────────────────────────
def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    fetch_film()
    shutil.copytree(HERE / "static", out / "static")
    releases = parse_changelog()
    latest = releases[0]

    tutorials = []
    for p in sorted((HERE / "tutorials").glob("*.md")):
        meta, body = front_matter(p.read_text())
        tutorials.append({"slug": p.stem, "title": meta.get("title", p.stem), "summary": meta.get("summary", ""),
                          "order": int(meta.get("order", 99)), "body": body})
    tutorials.sort(key=lambda t: t["order"])

    # Landing page
    page = (HERE / "index.html").read_text()
    svg = (HERE / "static/img/pipeline-map.svg").read_text()
    jsonld = {
        "@context": "https://schema.org", "@type": "SoftwareSourceCode",
        "name": "MuSA", "alternateName": "Multi-Source variant Annotation",
        "description": "Nextflow pipeline that turns a germline VCF into one annotated row per variant and a self-contained HTML report for rare-disease review.",
        "codeRepository": REPO_URL, "url": SITE_URL, "programmingLanguage": "Nextflow",
        "license": "https://creativecommons.org/licenses/by-nc/4.0/", "version": latest["version"].lstrip("v"),
        "citation": "https://doi.org/10.1186/s12859-026-06513-0",
        "identifier": f"https://doi.org/{CONCEPT_DOI}",
        "sameAs": [REPO_URL, f"https://doi.org/{CONCEPT_DOI}"],
        "keywords": "germline variant annotation, Ensembl VEP, ClinVar, HPO, dbNSFP, rare disease, Nextflow",
    }
    doi = VERSION_DOIS.get(latest["version"])
    hl = "".join(f"<li>{md_inline(h)}</li>" for h in latest["highlights"][:6])
    page = (page.replace("<!--MAP-->", svg)
                .replace("{{NAV}}", nav("", "")).replace("{{FOOTER}}", footer(""))
                .replace("{{SITE_URL}}", SITE_URL).replace("{{JSONLD}}", json.dumps(jsonld))
                .replace("{{REL_TITLE}}", html.escape(latest["intro"] or f"MuSA {latest['version']}"))
                .replace("{{REL_VERSION}}", latest["version"]).replace("{{REL_DATE}}", latest["date"])
                .replace("{{REL_GITHUB}}", f"{REPO_URL}/releases/tag/{latest['version']}")
                .replace("{{REL_DOI}}", f'<p class="date" style="margin-top:22px">Zenodo: <a href="https://doi.org/{doi}">{doi}</a></p>' if doi else "")
                .replace("{{REL_BODY}}", f"<ul>{hl}</ul>")
                .replace("{{REL_SHORT}}", latest["version"].lstrip("v")))
    (out / "index.html").write_text(page)

    # Documentation
    for i, (slug, src, title) in enumerate(DOCS):
        text = (REPO / src).read_text()
        text = re.sub(r"^# MuSA: ", "# ", text, count=1)
        body = rewrite_doc_links(md_to_html(text), "../../")
        prev = (DOCS[i - 1][2], f"docs/{DOCS[i - 1][0]}/") if i else None
        nxt = (DOCS[i + 1][2], f"docs/{DOCS[i + 1][0]}/") if i + 1 < len(DOCS) else None
        render_page(out, f"docs/{slug}/index.html", title=title, description=f"MuSA documentation: {title.lower()}.",
                    content=body, current=f"docs/{slug}", tutorials=tutorials, releases=releases,
                    pager=pager_html("../../", prev, nxt))
    (out / "docs/index.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=usage/"><link rel="canonical" href="usage/"><a href="usage/">Usage</a>')

    # Tutorials
    cards = "".join(f'<h2><a href="{t["slug"]}/">{html.escape(t["title"])}</a></h2><p>{html.escape(t["summary"])}</p>' for t in tutorials)
    render_page(out, "tutorials/index.html", title="Tutorials", description="Step-by-step MuSA tutorials.",
                content=f"<h1>Tutorials</h1>{cards}", current="tutorials", tutorials=tutorials, releases=releases)
    for i, t in enumerate(tutorials):
        prev = (tutorials[i - 1]["title"], f"tutorials/{tutorials[i - 1]['slug']}/") if i else None
        nxt = (tutorials[i + 1]["title"], f"tutorials/{tutorials[i + 1]['slug']}/") if i + 1 < len(tutorials) else None
        render_page(out, f"tutorials/{t['slug']}/index.html", title=t["title"], description=t["summary"],
                    content=md_to_html(t["body"]), current=f"tutorials/{t['slug']}", tutorials=tutorials,
                    releases=releases, pager=pager_html("../../", prev, nxt))

    # Releases
    render_page(out, "releases/index.html", title="Releases", description="MuSA release notes and DOIs.",
                content=releases_page(releases), current="releases", tutorials=tutorials, releases=releases)

    # Example report: the real file, with a thin bar on top that says what it is.
    ex = (HERE / "example/NA12878_basic.html").read_text()
    bar = ('<div style="font:500 14px/1.5 Poppins,system-ui,sans-serif;background:#0d1117;color:#e6e8f2;padding:10px 16px;'
           'display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center">'
           '<a href="../" style="color:#8f86ff;text-decoration:none">← MuSA</a>'
           f'<span>Example report · NA12878 reference sample with a test phenotype · basic mode · MuSA {latest["version"]}</span>'
           '<span style="color:#a9abbd">Public reference data, not a patient.</span></div>')
    ex = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + bar, ex, count=1)
    (out / "example").mkdir(parents=True, exist_ok=True)
    (out / "example/index.html").write_text(ex)

    # Machine-readable files: llms.txt, robots.txt, sitemap.xml
    llms = (HERE / "llms.txt").read_text().replace("{{VERSION}}", latest["version"])
    (out / "llms.txt").write_text(llms)
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}sitemap.xml\n")
    pages = [""] + [f"docs/{s}/" for s, _, _ in DOCS] + ["tutorials/"] + [f"tutorials/{t['slug']}/" for t in tutorials] + ["releases/", "example/", "llms.txt"]
    urls = "".join(f"<url><loc>{SITE_URL}{p}</loc></url>" for p in pages)
    (out / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n')
    render_page(out, "404.html", title="Not found", description="Page not found.",
                content='<h1>Not found</h1><p>That page doesn\'t exist. Start from the <a href="/MuSA/">MuSA home page</a>.</p>',
                current="", tutorials=tutorials, releases=releases)
    # 404.html is served from any depth, so its relative links must be absolute.
    p404 = (out / "404.html").read_text().replace('href="static/', 'href="/MuSA/static/').replace('src="static/', 'src="/MuSA/static/')
    p404 = re.sub(r'href="(?!https?:|/|#)([^"]*)"', r'href="/MuSA/\1"', p404)
    (out / "404.html").write_text(p404)
    print(f"Built {out} ({latest['version']}, {len(tutorials)} tutorials, {len(releases)} releases)")


def md_inline(text: str) -> str:
    h = markdown.markdown(text)
    return re.sub(r"^<p>|</p>$", "", h.strip())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=REPO / "_site")
    build(ap.parse_args().out.resolve())
