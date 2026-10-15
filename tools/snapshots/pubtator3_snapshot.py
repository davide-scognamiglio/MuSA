#!/usr/bin/env python3
"""Build MuSA's PubTator3 snapshot: variant -> PubMed articles that mention it.

Maintainer tool, run once per MuSA release; users download the result at setup.

    pubtator3_snapshot.py mutation2pubtator3.gz MANE.summary.txt.gz OUT_DIR YYYY-MM-DD

NCBI's mutation2pubtator3.gz lists every variant mention PubTator3 found in PubMed and PMC, plus the
articles ClinVar and dbSNP cite, one row per article and variant concept. NCBI keeps no older
versions, so the file is archived as is next to the index, and the index is what MuSA reads:

    pubtator3_index.tsv.gz   key <TAB> PMIDs with their sources, newest first
      key   "rs121908062"            a variant PubTator3 normalised to dbSNP
            "PAH:p.Y414C"            gene symbol + protein change (one-letter, stop as X)
            "PAH:c.1241A>G"          gene symbol + cDNA change, as the paper numbers it
      PMIDs "30455462:T,15172000:C"  T text-mined by PubTator3, C cited by ClinVar,
                                     D cited by dbSNP/dbGaP; several letters when several sources

Gene-scoped keys need PubTator3's CorrespondingGene (an NCBI Gene id), mapped to the symbol MuSA
writes through the MANE summary. A protein or cDNA mention with no gene, or with a gene outside
MANE, is left out: "p.Y414C" alone could be any protein.
"""

import gzip
import hashlib
import os
import re
import shutil
import sys
from collections import defaultdict

SOURCE = {"PubTator3": "T", "ClinVar": "C", "dbSNP": "D", "dbGAP": "D"}
RS = re.compile(r"^rs\d+$")
HGVS = re.compile(r"HGVS:([pc]\.[^;]+)")
GENE = re.compile(r"CorrespondingGene:([\d;,]+)")


def main():
    src, mane, out, date = sys.argv[1:5]
    os.makedirs(out, exist_ok=True)
    ent2sym = {}
    with gzip.open(mane, "rt") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        i_id, i_sym = header.index("#NCBI_GeneID"), header.index("symbol")
        for line in fh:
            f = line.rstrip("\n").split("\t")
            ent2sym[f[i_id].split(":")[1]] = f[i_sym]

    index = defaultdict(dict)   # key -> pmid -> set of source letters
    rows = kept = 0
    with gzip.open(src, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 5:
                continue
            rows += 1
            pmid, concept, sources = f[0], f[2], f[4]
            letters = {SOURCE[s] for s in sources.split("|") if s in SOURCE}
            keys = []
            if RS.match(concept):
                keys.append(concept)
            else:
                h, g = HGVS.search(concept), GENE.search(concept)
                if h and g:
                    change = h.group(1).replace("*", "X")
                    for ent in re.split(r"[;,]", g.group(1)):
                        if ent in ent2sym:
                            keys.append(f"{ent2sym[ent]}:{change}")
            for k in keys:
                index[k].setdefault(pmid, set()).update(letters)
            kept += bool(keys)

    path = f"{out}/pubtator3_index.tsv.gz"
    with gzip.open(path, "wt") as fh:
        fh.write("key\tpmids\n")
        for key in sorted(index):
            pmids = sorted(index[key].items(), key=lambda kv: -int(kv[0]) if kv[0].isdigit() else 0)
            fh.write(key + "\t" + ",".join(f"{p}:{''.join(sorted(s)) or 'T'}" for p, s in pmids) + "\n")
    archived = f"{out}/mutation2pubtator3_{date}.gz"
    shutil.copyfile(src, archived)
    with open(f"{out}/SOURCES_pubtator3.txt", "w") as fh:
        fh.write(f"PubTator3 snapshot for MuSA, {date}\n"
                 "Source: https://ftp.ncbi.nlm.nih.gov/pub/lu/PubTator3/mutation2pubtator3.gz "
                 "(NCBI, US government work, public domain)\n"
                 f"Rows read: {rows}; rows with a usable key: {kept}; index keys: {len(index)}\n"
                 "Gene ids mapped to symbols with the MANE summary given to the build.\n")
    with open(f"{out}/SHA256SUMS_pubtator3", "w") as fh:
        for p in (path, archived, f"{out}/SOURCES_pubtator3.txt"):
            fh.write(f"{hashlib.sha256(open(p, 'rb').read()).hexdigest()}  {os.path.basename(p)}\n")
    print(f"{path}: {len(index)} keys from {kept} of {rows} rows")


if __name__ == "__main__":
    main()
