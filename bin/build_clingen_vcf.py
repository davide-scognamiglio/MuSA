#!/usr/bin/env python3
"""
MuSA — build_clingen_vcf.py

Build a ClinGen Variant Pathogenicity VCF from the ClinGen Evidence Repository
(ERepo) tabbed export, for use as a VEP --custom annotation (mirrors ClinVar).

For each ERepo record we take the genomic HGVS (NC_0000..:g...) from the
"HGVS Expressions" field, map the RefSeq chromosome accession to a chr-prefixed
contig (matching hg38.fa), and emit an SNV VCF record with INFO:
    Assertion       — expert-panel classification (Pathogenic/Likely_Pathogenic/…)
    EvidenceCodes   — applied ACMG codes (met)
    Disease         — disease label / MONDO

Only single-nucleotide substitutions (g.<pos><REF>><ALT>) are emitted — VEP
--custom type=exact needs exact REF/ALT and a reference base we do not have here
for indels; complex/indel assertions are counted and skipped (documented limit).
Records are coordinate-sorted so the caller can bgzip + tabix directly.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys

# RefSeq GRCh38 chromosome accessions (WITH version) → chr-prefixed contigs (match
# hg38.fa). Versions are pinned to GRCh38 because the ERepo "HGVS Expressions" field
# lists the same variant on multiple assemblies (e.g. NC_000007.14=GRCh38, .13=GRCh37,
# .12=GRCh36); accepting a bare accession would silently pull GRCh37 coordinates.
NC_TO_CHR = {
    "NC_000001.11": "chr1",  "NC_000002.12": "chr2",  "NC_000003.12": "chr3",
    "NC_000004.12": "chr4",  "NC_000005.10": "chr5",  "NC_000006.12": "chr6",
    "NC_000007.14": "chr7",  "NC_000008.11": "chr8",  "NC_000009.12": "chr9",
    "NC_000010.11": "chr10", "NC_000011.10": "chr11", "NC_000012.12": "chr12",
    "NC_000013.11": "chr13", "NC_000014.9": "chr14",  "NC_000015.10": "chr15",
    "NC_000016.10": "chr16", "NC_000017.11": "chr17", "NC_000018.10": "chr18",
    "NC_000019.10": "chr19", "NC_000020.11": "chr20", "NC_000021.9": "chr21",
    "NC_000022.11": "chr22", "NC_000023.11": "chrX",  "NC_000024.10": "chrY",
    "NC_012920.1": "chrM",
}

# Genomic SNV HGVS with explicit accession version, e.g. "NC_000011.10:g.108236168A>G".
_G_SNV = re.compile(r"(NC_\d{6}\.\d+):g\.(\d+)([ACGT])>([ACGT])", re.IGNORECASE)


def _sanitize(v: str) -> str:
    """VCF INFO-safe: no spaces/semicolons/commas/equals/tabs."""
    if not v:
        return "."
    v = re.sub(r"\s+", "_", v.strip())
    v = v.replace(";", "|").replace(",", "/").replace("=", "-").replace("\t", "_")
    return v or "."


def _find_header(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            low = line.lower()
            if "hgvs expressions" in low and "assertion" in low:
                header = next(csv.reader([line.rstrip("\n")], delimiter="\t"))
                return i, [h.lstrip("#").strip() for h in header]
    raise ValueError(f"{path}: no ERepo header (needs 'HGVS Expressions' + 'Assertion')")


def _col(header, *needles):
    for i, h in enumerate(header):
        low = h.lower()
        if all(n in low for n in needles):
            return i
    return None


def build(erepo, out_vcf):
    skip, header = _find_header(erepo)
    h_i = _col(header, "hgvs expressions")
    a_i = _col(header, "assertion")
    e_i = _col(header, "applied evidence codes", "met") or _col(header, "evidence codes")
    d_i = _col(header, "disease") or _col(header, "mondo")

    records = {}   # (chrom, pos, ref, alt) -> (info dict) ; dedup keeps first
    kept = skipped = 0
    with open(erepo, encoding="utf-8", errors="replace") as fh:
        for _ in range(skip + 1):
            next(fh, None)
        for rec in csv.reader(fh, delimiter="\t"):
            if not rec or h_i is None or h_i >= len(rec):
                continue
            # The HGVS list carries the variant on several assemblies — scan all
            # genomic SNV matches and take the one on a GRCh38 chromosome accession.
            chrom = pos = ref = alt = None
            for m in _G_SNV.finditer(rec[h_i]):
                c = NC_TO_CHR.get(m.group(1).upper())
                if c is not None:
                    chrom, pos, ref, alt = c, m.group(2), m.group(3).upper(), m.group(4).upper()
                    break
            if chrom is None:
                skipped += 1
                continue
            key = (chrom, int(pos), ref, alt)
            if key in records:
                continue
            records[key] = {
                "Assertion": _sanitize(rec[a_i] if a_i is not None and a_i < len(rec) else ""),
                "EvidenceCodes": _sanitize(rec[e_i] if e_i is not None and e_i < len(rec) else ""),
                "Disease": _sanitize(rec[d_i] if d_i is not None and d_i < len(rec) else ""),
            }
            kept += 1

    chrom_order = {c: i for i, c in enumerate(
        [f"chr{n}" for n in range(1, 23)] + ["chrX", "chrY", "chrM"])}
    keys = sorted(records, key=lambda k: (chrom_order.get(k[0], 99), k[1], k[2], k[3]))

    with open(out_vcf, "w", encoding="utf-8", newline="") as out:
        out.write("##fileformat=VCFv4.2\n")
        out.write("##source=ClinGen_ERepo\n")
        out.write('##INFO=<ID=Assertion,Number=1,Type=String,Description="ClinGen VCEP assertion">\n')
        out.write('##INFO=<ID=EvidenceCodes,Number=1,Type=String,Description="Applied ACMG evidence codes (met)">\n')
        out.write('##INFO=<ID=Disease,Number=1,Type=String,Description="ClinGen disease label/MONDO">\n')
        out.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
        for (chrom, pos, ref, alt) in keys:
            info = records[(chrom, pos, ref, alt)]
            info_str = f"Assertion={info['Assertion']};EvidenceCodes={info['EvidenceCodes']};Disease={info['Disease']}"
            out.write(f"{chrom}\t{pos}\t.\t{ref}\t{alt}\t.\t.\t{info_str}\n")

    print(f"[INFO] ClinGen pathogenicity VCF: {kept} SNV records, {skipped} skipped "
          f"(non-SNV/indel/unmapped) -> {out_vcf}", file=sys.stderr)
    return kept


def main():
    ap = argparse.ArgumentParser(description="ERepo tabbed export → ClinGen pathogenicity VCF (SNV).")
    ap.add_argument("--input", required=True, help="erepo.tabbed.txt")
    ap.add_argument("--output", required=True, help="output .vcf (uncompressed; caller bgzips)")
    args = ap.parse_args()
    build(args.input, args.output)


if __name__ == "__main__":
    main()
