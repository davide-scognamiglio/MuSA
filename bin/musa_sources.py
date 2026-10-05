#!/usr/bin/env python3
"""Check and render MuSA's annotation-source catalogue (assets/annotation_sources.yaml).

    musa_sources.py check  --maf NA12878.raw.maf --sample HG001 [--extended] [--online]
    musa_sources.py render [--docs docs/sources.md] [--readme README.md]

`check` is what keeps the catalogue honest: every column of a real MAF must belong to exactly one
source, and every source active in that run's mode must have at least one column in it. A column
the catalogue does not know about, or a source whose columns vanished after a tool update, fails it.

`render` writes docs/sources.md and the block between the `<!-- sources:start -->` and
`<!-- sources:end -->` markers in README.md. Run it after editing the catalogue.

This is a development tool (it needs PyYAML, which the pipeline images do not ship); at run time
Nextflow reads the catalogue itself (lib/annot_utils.nf).
"""

import argparse
import re
import sys
from collections import OrderedDict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "assets" / "annotation_sources.yaml"

LEVELS = OrderedDict([
    ("variant", "Variant level"),
    ("gene", "Gene level"),
    ("score", "Scores and classification"),
    ("filter", "Filtering"),
])
MODE_LABEL = {"basic": "basic", "extended": "extended (`--use_vep_plugins true`)",
              "online": "online (`--offline false`)"}


def load(path=CATALOGUE):
    data = yaml.safe_load(Path(path).read_text())
    providers, sources = data["providers"], data["sources"]
    for s in sources:
        p = providers[s["provider"]]
        s.setdefault("kind", "resource")
        s.setdefault("mode", p["mode"])
        s.setdefault("columns", [])
    return providers, sources


def is_counted(source):
    """Only external knowledge counts as an annotation source; derived fields do not."""
    return source["kind"] == "resource" and source["level"] != "format"


def active(source, extended, online):
    return {"basic": True, "extended": extended, "online": online}[source["mode"]]


# ── check ─────────────────────────────────────────────────────────────────────────────────────────
def check(args):
    _, sources = load(args.catalogue)
    header = Path(args.maf).open().readline().rstrip("\n").split("\t")

    patterns = []
    for s in sources:
        for col in s["columns"]:
            regex = re.escape(args.sample) if col == "{sample}" else col
            patterns.append((s["id"], re.compile(regex)))

    owners, unknown, ambiguous = {}, [], []
    for col in header:
        hits = sorted({sid for sid, rx in patterns if rx.fullmatch(col)})
        if not hits:
            unknown.append(col)
        elif len(hits) > 1:
            ambiguous.append(f"{col} ({', '.join(hits)})")
        else:
            owners.setdefault(hits[0], []).append(col)

    missing = [s["id"] for s in sources
               if s["columns"] and active(s, args.extended, args.online) and s["id"] not in owners]

    mode = "extended" if args.extended else "basic"
    mode += ", online" if args.online else ", offline"
    print(f"{args.maf}: {len(header)} columns, {mode}")
    print(f"  attributed to {len(owners)} sources "
          f"({sum(1 for s in sources if s['id'] in owners and is_counted(s))} counted as annotation sources)")
    for label, items in (("columns no source claims", unknown),
                         ("columns claimed by more than one source", ambiguous),
                         ("active sources with no column in this MAF", missing)):
        if items:
            print(f"  {label}: {', '.join(items)}")
    if unknown or ambiguous or missing:
        sys.exit(1)
    print("  OK")


# ── render ────────────────────────────────────────────────────────────────────────────────────────
def provider_cell(source, providers):
    p = providers[source["provider"]]
    name = source.get("plugin") and f"VEP plugin {source['plugin']}" or p["name"]
    return f"{name} (`{p['step']}`)"


def render_docs(providers, sources):
    counted = [s for s in sources if is_counted(s)]
    out = [
        "# MuSA: Annotation sources",
        "",
        "<!-- Generated from assets/annotation_sources.yaml by bin/musa_sources.py render. "
        "Edit the catalogue, not this file. -->",
        "",
        f"MuSA annotates every variant from **{len(counted)} sources**: "
        f"{sum(1 for s in counted if s['level'] == 'variant')} at variant level, "
        f"{sum(1 for s in counted if s['level'] == 'gene')} at gene level, plus classification "
        "and filtering. Each row says what the source adds, which step brings it in, when it is "
        "active, and the MAF columns it fills (regular expressions).",
        "",
        "When a run starts, MuSA prints the same list with the versions installed in `--data_dir`, "
        "and the report's **Annotation sources** view records what that run actually used.",
        "",
        "Modes: **basic** is always on; **extended** needs `setup --download_vep_plugins true` and "
        "`annotate --use_vep_plugins true`; **online** needs `--offline false` (GeneBe credentials "
        "for ACMG).",
        "",
    ]
    for level, title in LEVELS.items():
        group = [s for s in sources if s["level"] == level]
        if not group:
            continue
        out += [f"## {title}", ""]
        categories = OrderedDict()
        for s in group:
            categories.setdefault(s["category"], []).append(s)
        for cat, items in categories.items():
            out += [f"### {cat}", "",
                    "| Source | What it adds | Brought in by | Mode | Columns |",
                    "|---|---|---|---|---|"]
            for s in items:
                cols = ", ".join(f"`{c}`" for c in s["columns"]) or "none (filters rows)"
                what = s["what"] + (f" *{s['note']}*" if s.get("note") else "")
                name = s["name"] + (" ⁽ᶜ⁾" if s["kind"] == "computed" else "")
                out.append(f"| {name} | {what} | {provider_cell(s, providers)} | "
                           f"{s['mode']} | {cols} |")
            out.append("")
    fmt = [s for s in sources if s["level"] == "format"]
    out += ["## Call information and MAF format", "",
            "Not annotation sources, but every column of the MAF is accounted for:", "",
            "| Fields | What they hold | Columns |", "|---|---|---|"]
    for s in fmt:
        out.append(f"| {s['name']} | {s['what']} | "
                   + ", ".join(f"`{c}`" for c in s["columns"]) + " |")
    out += ["", "⁽ᶜ⁾ derived by a tool rather than taken from an external resource; not counted "
            "among the sources above.", ""]
    return "\n".join(out)


def render_readme_block(sources):
    counted = [s for s in sources if is_counted(s)]
    rows = OrderedDict()
    for s in counted:
        rows.setdefault((s["level"], s["category"]), []).append(s)
    out = [
        "<!-- sources:start (generated by bin/musa_sources.py render; edit "
        "assets/annotation_sources.yaml) -->",
        f"**{len(counted)} annotation sources**, merged into one row per variant "
        "(full list with columns and versions: [`docs/sources.md`](docs/sources.md)):",
        "",
        "| Level | Evidence | Sources |",
        "|---|---|---|",
    ]
    for (level, cat), items in rows.items():
        names = ", ".join(s["name"] + ("*" if s["mode"] != "basic" else "") for s in items)
        out.append(f"| {LEVELS[level].split()[0]} | {cat} | {names} |")
    out += ["",
            "\\* extended mode (VEP plugins) or online mode (GeneBe, HPO panel) only.",
            "<!-- sources:end -->"]
    return "\n".join(out)


def render(args):
    providers, sources = load(args.catalogue)
    if args.docs:
        Path(args.docs).write_text(render_docs(providers, sources))
        print(f"wrote {args.docs}")
    if args.readme:
        text = Path(args.readme).read_text()
        block = render_readme_block(sources)
        new, n = re.subn(r"<!-- sources:start.*?<!-- sources:end -->", lambda _: block, text,
                         flags=re.S)
        if n != 1:
            sys.exit(f"{args.readme}: expected one <!-- sources:start --> ... "
                     "<!-- sources:end --> block")
        Path(args.readme).write_text(new)
        print(f"updated {args.readme}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--catalogue", default=CATALOGUE)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--maf", required=True)
    c.add_argument("--sample", required=True, help="the patient's genotype column name")
    c.add_argument("--extended", action="store_true")
    c.add_argument("--online", action="store_true")
    r = sub.add_parser("render")
    r.add_argument("--docs")
    r.add_argument("--readme")
    args = ap.parse_args()
    {"check": check, "render": render}[args.cmd](args)


if __name__ == "__main__":
    main()
