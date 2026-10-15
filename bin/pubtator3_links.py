#!/usr/bin/env python3
"""PubMed articles that mention the variant, from PubTator3.

    pubtator3_links.py build    mutation2pubtator3.gz MANE.summary.txt.gz pubtator3_index.tsv.gz
    pubtator3_links.py annotate --maf in.maf --index pubtator3_index.tsv.gz --output out.maf

build (setup)
    NCBI's mutation2pubtator3.gz lists every variant mention PubTator3 found in PubMed and PMC, plus
    the articles ClinVar and dbSNP cite, one row per article and variant concept. The index maps
        "rs121908062"     a variant PubTator3 normalised to dbSNP
        "PAH:p.Y414C"     gene symbol + protein change (one-letter, stop as X)
        "PAH:c.1241A>G"   gene symbol + cDNA change, as the paper numbers it
    to "PMID:sources" items, newest first (T text-mined, C cited by ClinVar, D cited by dbSNP/dbGaP).
    Gene-scoped keys need PubTator3's CorrespondingGene (an NCBI Gene id), mapped to the symbol MuSA
    writes through the MANE summary; a protein or cDNA mention with no gene, or a gene outside MANE,
    is left out ("p.Y414C" alone could be any protein). NCBI replaces the file in place, so the
    index reflects the day setup ran; the setup report records the file's checksum.

annotate
    A MAF row is looked up three ways and the articles are pooled:
  - its dbSNP ids (rs... in Existing_variation),
  - gene + protein change ("PAH:p.Y414C", from Hugo_Symbol and HGVSp_VEP),
  - gene + cDNA change ("PAH:c.1241A>G", from HGVSc).
The cDNA form matches only papers that number the variant on the same transcript; synonymous
protein changes are not looked up (a paper's "p.L12=" does not identify the nucleotide change).

Adds three columns, "." when nothing is found:
  PubTator3_n       how many articles in all
  PubTator3_pmids   up to 50 of them: those ClinVar cites first, then text-mined, then dbSNP-cited,
                    newest first within each group
  PubTator3_source  for each listed PMID, in the same order: ClinVar, text-mined or dbSNP, joined
                    with "+" when several apply

This complements VEP's PUBMED column (articles dbSNP links to the variant's rsID); both are kept.
"""

import argparse
import gzip
import os
import re
import sys
from collections import defaultdict

MAX_PMIDS = 50
SOURCE_NAME = {"C": "ClinVar", "T": "text-mined", "D": "dbSNP"}
RANK = {"C": 0, "T": 1, "D": 2}
AA3 = {"Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C", "Gln": "Q", "Glu": "E", "Gly": "G",
       "His": "H", "Ile": "I", "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P", "Ser": "S",
       "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V", "Ter": "X"}
PROTEIN = re.compile(r"^p\.\(?([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2})\)?$")
RSID = re.compile(r"\brs\d+\b")
COLUMNS = ["PubTator3_n", "PubTator3_pmids", "PubTator3_source"]
SOURCE_LETTER = {"PubTator3": "T", "ClinVar": "C", "dbSNP": "D", "dbGAP": "D"}
RS_CONCEPT = re.compile(r"^rs\d+$")
HGVS = re.compile(r"HGVS:([pc]\.[^;]+)")
GENE = re.compile(r"CorrespondingGene:([\d;,]+)")


# ── build ─────────────────────────────────────────────────────────────────────────────────────────
def build(args):
    ent2sym = {}
    with gzip.open(args.mane, "rt") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        i_id, i_sym = header.index("#NCBI_GeneID"), header.index("symbol")
        for line in fh:
            f = line.rstrip("\n").split("\t")
            ent2sym[f[i_id].split(":")[1]] = f[i_sym]

    index = defaultdict(dict)   # key -> pmid -> set of source letters
    rows = kept = 0
    with gzip.open(args.pubtator, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 5:
                continue
            rows += 1
            pmid, concept, sources = f[0], f[2], f[4]
            letters = {SOURCE_LETTER[s] for s in sources.split("|") if s in SOURCE_LETTER}
            found = []
            if RS_CONCEPT.match(concept):
                found.append(concept)
            else:
                h, g = HGVS.search(concept), GENE.search(concept)
                if h and g:
                    change = h.group(1).replace("*", "X")
                    found += [f"{ent2sym[e]}:{change}" for e in re.split(r"[;,]", g.group(1)) if e in ent2sym]
            for k in found:
                index[k].setdefault(pmid, set()).update(letters)
            kept += bool(found)

    with gzip.open(args.output, "wt") as fh:
        fh.write("key\tpmids\n")
        for key in sorted(index):
            pmids = sorted(index[key].items(), key=lambda kv: -int(kv[0]) if kv[0].isdigit() else 0)
            fh.write(key + "\t" + ",".join(f"{p}:{''.join(sorted(s)) or 'T'}" for p, s in pmids) + "\n")
    print(f"{args.output}: {len(index)} keys from {kept} of {rows} PubTator3 rows")


# ── annotate ──────────────────────────────────────────────────────────────────────────────────────


def keys(row, col):
    out = RSID.findall(row[col["Existing_variation"]]) if "Existing_variation" in col else []
    gene = row[col["Hugo_Symbol"]] if "Hugo_Symbol" in col else ""
    if gene and gene != ".":
        m = PROTEIN.match(row[col["HGVSp_VEP"]] if "HGVSp_VEP" in col else "")
        if m and m.group(1) in AA3 and m.group(3) in AA3 and m.group(1) != m.group(3):
            out.append(f"{gene}:p.{AA3[m.group(1)]}{m.group(2)}{AA3[m.group(3)]}")
        c = row[col["HGVSc"]].split(":")[-1] if "HGVSc" in col else ""
        if c.startswith("c."):
            out.append(f"{gene}:{c}")
    return out


def annotate(args):
    if not os.path.isfile(args.index):
        sys.exit(f"{args.index} not found: this data directory predates MuSA 1.5's PubTator3 index. "
                 "Run `--workflow setup --update_db_only true` once to add it.")

    with open(args.maf, newline="\n") as fin:
        header = fin.readline().rstrip("\n").split("\t")
        col = {}
        for i, name in enumerate(header):
            col.setdefault(name, i)
        rows = [line.rstrip("\n").split("\t") for line in fin]
    row_keys = [keys(r, col) for r in rows]
    wanted = {k for ks in row_keys for k in ks}

    # The index holds ~2.5 million keys; only the MAF's are kept in memory.
    index = {}
    with gzip.open(args.index, "rt") as fh:
        if fh.readline().rstrip("\n") != "key\tpmids":
            sys.exit(f"{args.index}: unexpected header; rebuild it with this MuSA version's setup")
        for line in fh:
            key, _, pmids = line.rstrip("\n").partition("\t")
            if key in wanted:
                index[key] = pmids

    n_hit = 0
    with open(args.output, "w", newline="\n") as fout:
        fout.write("\t".join(header + COLUMNS) + "\n")
        for r, ks in zip(rows, row_keys):
            found = {}
            for k in ks:
                for item in index.get(k, "").split(","):
                    if item:
                        pmid, _, letters = item.partition(":")
                        found[pmid] = found.get(pmid, "") + letters
            if not found:
                fout.write("\t".join(r + ["."] * len(COLUMNS)) + "\n")
                continue
            n_hit += 1
            ranked = sorted(found.items(), key=lambda kv: (min(RANK.get(c, 9) for c in kv[1]),
                                                           -int(kv[0]) if kv[0].isdigit() else 0))
            listed = ranked[:MAX_PMIDS]
            sources = ["+".join(SOURCE_NAME[c] for c in sorted(set(letters), key=RANK.get) if c in SOURCE_NAME)
                       for _, letters in listed]
            fout.write("\t".join(r + [str(len(found)), ",".join(p for p, _ in listed),
                                      ",".join(sources)]) + "\n")
    print(f"{args.output}: PubTator3 articles for {n_hit} of {len(rows)} variants", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("pubtator")
    b.add_argument("mane")
    b.add_argument("output")
    a = sub.add_parser("annotate")
    a.add_argument("--maf", required=True)
    a.add_argument("--index", required=True)
    a.add_argument("--output", required=True)
    args = ap.parse_args()
    {"build": build, "annotate": annotate}[args.cmd](args)


if __name__ == "__main__":
    main()
