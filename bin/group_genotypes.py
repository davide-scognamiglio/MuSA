#!/usr/bin/env python3
"""Member genotypes and group facts for a family or a cohort annotated from one joint-called VCF.

    group_genotypes.py --maf in.maf --members members.tsv --mode family|cohort --output out.maf
                       [--sidecar genotypes.tsv.gz] [--max-member-columns 10]
                       [--genes genes.tsv] [--rare-af 0.01]
                       [--dn-min-dp 10] [--dn-min-gq 20] [--dn-max-parent-alt 0]

members.tsv: sample, role, sex, affected, family per line, in meta.members order (samplesheet
order, proband first). The MAF's GROUP_FORMAT_VALUES column (from PARSE_VEP_ANNOTATION) holds every
member's FORMAT values on each row in that same order, picked from the VCF by sample name (the VCF's
own column order is not relied on: GATK sorts it); it is read and dropped.

Every mode:
  GT_<sample>, DP_<sample>, GQ_<sample>, AD_<sample>, VAF_<sample>  for each member, or, with more
  members than --max-member-columns, one line per carrier genotype in the --sidecar table instead.

Family mode (a proband, its parents, possibly siblings and relatives):
  Inheritance            where the proband's alternate allele comes from:
                           de_novo, maternal, paternal, biparental (homozygous, one allele from
                           each parent), not_in_proband, unknown
  Inheritance_check      pass, unchecked (the VCF has no DP/GQ/AD to check a de novo call with),
                           parent_missing, parent_no_call, parent_low_depth, parent_low_gq,
                           parent_alt_reads, proband_no_call, proband_low_gq, proband_allele_balance,
                           both_parents_carry, mendelian_error
  Segregation_affected   carriers among affected members / affected members called ("2/2")
  Segregation_unaffected carriers among unaffected members / unaffected members called
  Comphet_trans          the proband's other heterozygous variants in the same gene that come from
                           the other parent: the two are in trans
  Comphet_cis_or_unknown its other heterozygous variants in the gene whose phase the trio does not
                           establish (same parent, de novo, or unknown origin)

Cohort mode (cases, mostly unrelated):
  Cohort_called_n, Cohort_carriers_n, Cohort_het_n, Cohort_hom_n, Cohort_AF,
  Cohort_carrier_families_n (relatives counted once, via the samplesheet `family` column),
  Cohort_affected_carriers_n, Cohort_unaffected_carriers_n, Cohort_carriers (up to 50 names);
  a hemizygous carrier counts in Cohort_het_n.
  --genes: one line per gene, members and families carrying its variants, overall and for rare
  (MAX_AF below --rare-af, or absent from the population databases) HIGH / MODERATE impact
  variants, split by affected status. Counts over every variant of the group, before the run's
  panel and HPO filters; no statistic is computed.

These are facts about genotypes, not ACMG criteria. Parentage is assumed. chrX outside the
pseudoautosomal regions in a male proband can only be maternal or de novo, chrY only paternal or
de novo; PAR1 and PAR2 (GRCh38) are treated as autosomal.
"""

import argparse
import gzip
import re
import sys
from collections import defaultdict

MISSING = "."
SPLIT_GT = re.compile(r"[/|]")
MEMBER_FIELDS = ["GT", "DP", "GQ", "AD", "VAF"]
FAMILY_COLUMNS = ["Inheritance", "Inheritance_check", "Segregation_affected",
                  "Segregation_unaffected", "Comphet_trans", "Comphet_cis_or_unknown"]
COHORT_COLUMNS = ["Cohort_called_n", "Cohort_carriers_n", "Cohort_het_n", "Cohort_hom_n",
                  "Cohort_AF", "Cohort_carrier_families_n", "Cohort_affected_carriers_n",
                  "Cohort_unaffected_carriers_n", "Cohort_carriers"]
MAX_CARRIERS_LISTED = 50
MAX_PARTNERS = 20
# GRCh38 pseudoautosomal regions, 1-based inclusive, identical coordinates on chrX and chrY.
PAR = [(10001, 2781479), (155701383, 156030895)]
MAF_KEY = ["Chromosome", "Start_Position", "Reference_Allele", "Tumor_Seq_Allele2"]


class Call:
    """One member's genotype at one site."""
    __slots__ = ("gt", "alleles", "dp", "gq", "ad", "vaf")

    def __init__(self, fields, values):
        f = dict(zip(fields, values.split(":"))) if values not in ("", MISSING) else {}
        get = lambda k: f.get(k, "") if f.get(k, "") not in ("", ".") else MISSING
        self.gt = get("GT")
        self.alleles = [a for a in SPLIT_GT.split(self.gt) if a not in ("", ".")] if self.gt != MISSING else []
        self.dp, self.gq, self.ad = get("DP"), get("GQ"), get("AD")
        self.vaf = MISSING
        if self.ad != MISSING:
            try:
                depths = [int(x) for x in self.ad.split(",")]
                total = sum(depths)
                if total and len(depths) > 1:
                    self.vaf = f"{sum(depths[1:]) / total:.2f}"
            except ValueError:
                pass

    @property
    def called(self):
        return bool(self.alleles)

    @property
    def carrier(self):
        return any(a != "0" for a in self.alleles)

    @property
    def ref(self):
        return self.called and not self.carrier

    @property
    def hom(self):
        return len(self.alleles) > 1 and self.carrier and len(set(self.alleles)) == 1

    def alt_reads(self):
        if self.ad == MISSING:
            return None
        try:
            return sum(int(x) for x in self.ad.split(",")[1:])
        except ValueError:
            return None

    def num(self, attr):
        try:
            return float(getattr(self, attr))
        except ValueError:
            return None

    def columns(self):
        return [self.gt, self.dp, self.gq, self.ad, self.vaf]


def read_members(path):
    members = []
    for line in open(path):
        if line.strip():
            sample, role, sex, affected, family = (line.rstrip("\n").split("\t") + [""] * 5)[:5]
            members.append({"sample": sample, "role": role, "sex": sex, "affected": affected,
                            "family": family or sample})
    return members


def region(chrom, pos, proband_sex):
    """autosomal (incl. PAR and a female proband's chrX), x_male, or y."""
    c = chrom.replace("chr", "")
    in_par = any(a <= pos <= b for a, b in PAR)
    if c == "X" and proband_sex == "male" and not in_par:
        return "x_male"
    if c == "Y" and not in_par:
        return "y"
    return "autosomal"


def de_novo_check(proband, parents, args):
    """'pass', 'unchecked' or the first failed condition for a de novo call."""
    if all(x.dp == MISSING and x.gq == MISSING and x.ad == MISSING for x in [proband] + parents):
        return "unchecked"
    for p in parents:
        dp, gq, alt = p.num("dp"), p.num("gq"), p.alt_reads()
        if dp is not None and dp < args.dn_min_dp:
            return "parent_low_depth"
        if gq is not None and gq < args.dn_min_gq:
            return "parent_low_gq"
        if alt is not None and alt > args.dn_max_parent_alt:
            return "parent_alt_reads"
    gq = proband.num("gq")
    if gq is not None and gq < args.dn_min_gq:
        return "proband_low_gq"
    vaf = proband.num("vaf")
    if vaf is not None and len(proband.alleles) > 1 and not proband.hom and not 0.25 <= vaf <= 0.75:
        return "proband_allele_balance"
    return "pass"


def inheritance(where, proband, mother, father, args):
    """(Inheritance, Inheritance_check) for one site."""
    if not proband.called:
        return "unknown", "proband_no_call"
    if not proband.carrier:
        return "not_in_proband", "pass"
    if where == "x_male":
        needed = [("mother", mother)]
    elif where == "y":
        needed = [("father", father)]
    else:
        needed = [("mother", mother), ("father", father)]
    for _, p in needed:
        if p is None:
            return "unknown", "parent_missing"
    for _, p in needed:
        if not p.called:
            return "unknown", "parent_no_call"
    carriers = [name for name, p in needed if p.carrier]

    if where in ("x_male", "y"):
        if carriers:
            return ("maternal" if where == "x_male" else "paternal"), "pass"
        check = de_novo_check(proband, [p for _, p in needed], args)
        return ("de_novo" if check in ("pass", "unchecked") else "unknown"), check

    if proband.hom:
        if len(carriers) == 2:
            return "biparental", "pass"
        return "unknown", "mendelian_error"
    if len(carriers) == 2:
        return "unknown", "both_parents_carry"
    if len(carriers) == 1:
        return ("maternal" if carriers[0] == "mother" else "paternal"), "pass"
    check = de_novo_check(proband, [mother, father], args)
    return ("de_novo" if check in ("pass", "unchecked") else "unknown"), check


def affected_status(m):
    """yes / no / unknown; a proband with no status given is affected (that is why it is one)."""
    if m["affected"] in ("yes", "no"):
        return m["affected"]
    return "yes" if m["role"] == "proband" else "unknown"


def segregation(calls, members, status):
    idx = [i for i, m in enumerate(members) if affected_status(m) == status]
    called = [i for i in idx if calls[i].called]
    if not called:
        return MISSING
    return f"{sum(calls[i].carrier for i in called)}/{len(called)}"


def label(row, col):
    gene = row[col["Hugo_Symbol"]] if "Hugo_Symbol" in col else ""
    p = row[col["HGVSp_VEP"]] if "HGVSp_VEP" in col else MISSING
    c = row[col["HGVSc"]].split(":")[-1] if "HGVSc" in col else MISSING
    change = p if p not in ("", MISSING) else (c if c not in ("", MISSING) else
             f"{row[col['Chromosome']]}:{row[col['Start_Position']]}"
             f"{row[col['Reference_Allele']]}>{row[col['Tumor_Seq_Allele2']]}")
    return f"{gene}:{change}" if gene not in ("", MISSING) else change


# Columns the facts read, besides FORMAT_FIELDS, GROUP_FORMAT_VALUES and the MAF key: kept for the
# first pass (label, region, the cohort gene table).
SLIM_COLUMNS = ["Hugo_Symbol", "HGVSp_VEP", "HGVSc", "IMPACT", "MAX_AF"]

GENE_COLUMNS = ["gene", "variants", "carriers", "carrier_families",
                "rare_high_carriers", "rare_moderate_carriers",
                "rare_high_or_moderate_carriers", "rare_high_or_moderate_families",
                "rare_high_or_moderate_affected", "rare_high_or_moderate_unaffected"]


def write_genes(args, rows, calls_by_row, col, members):
    """Cohort gene table: who carries each gene's variants, overall and rare HIGH/MODERATE."""
    gene_i, impact_i, af_i = col.get("Hugo_Symbol"), col.get("IMPACT"), col.get("MAX_AF")
    sets = defaultdict(lambda: defaultdict(set))
    n_variants = defaultdict(int)
    for r, calls in zip(rows, calls_by_row):
        gene = r[gene_i] if gene_i is not None else ""
        if gene in ("", MISSING):
            continue
        carriers = {i for i, c in enumerate(calls) if c.carrier}
        g = sets[gene]
        n_variants[gene] += 1
        g["any"] |= carriers
        impact = r[impact_i] if impact_i is not None else ""
        try:
            af = float(r[af_i]) if af_i is not None else None
        except ValueError:
            af = None
        if af is None or af < args.rare_af:
            if impact == "HIGH":
                g["high"] |= carriers
            elif impact == "MODERATE":
                g["moderate"] |= carriers
    fam = lambda idx: len({members[i]["family"] for i in idx})
    out = []
    for gene, g in sets.items():
        hm = g["high"] | g["moderate"]
        out.append([gene, n_variants[gene], len(g["any"]), fam(g["any"]), len(g["high"]),
                    len(g["moderate"]), len(hm), fam(hm),
                    sum(affected_status(members[i]) == "yes" for i in hm),
                    sum(affected_status(members[i]) == "no" for i in hm)])
    out.sort(key=lambda x: (-x[7], -x[6], -x[3], x[0]))
    with open(args.genes, "w") as fh:
        fh.write("\t".join(GENE_COLUMNS) + "\n")
        for line in out:
            fh.write("\t".join(map(str, line)) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--maf", required=True)
    ap.add_argument("--members", required=True)
    ap.add_argument("--mode", choices=["family", "cohort"], required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--sidecar")
    ap.add_argument("--max-member-columns", type=int, default=10)
    ap.add_argument("--dn-min-dp", type=float, default=10)
    ap.add_argument("--dn-min-gq", type=float, default=20)
    ap.add_argument("--dn-max-parent-alt", type=float, default=0)
    ap.add_argument("--genes")
    ap.add_argument("--rare-af", type=float, default=0.01)
    args = ap.parse_args()

    members = read_members(args.members)
    samples = [m["sample"] for m in members]
    wide = len(members) <= args.max_member_columns
    if not wide and not args.sidecar:
        sys.exit(f"{len(members)} members exceed --max-member-columns; give --sidecar")

    # Two passes over the MAF, so memory does not grow with its width: the first keeps, per row,
    # only the columns the facts are computed from; the second copies every row through with the
    # member columns and facts added. A joint-called family exome MAF (100,000 rows x 900 columns,
    # 0.5 GB) held whole took 6.5 GB.
    with open(args.maf, newline="\n") as fin:
        header = fin.readline().rstrip("\n").split("\t")
        full = {}
        for i, name in enumerate(header):
            full.setdefault(name, i)
        for need in ["FORMAT_FIELDS", "GROUP_FORMAT_VALUES"] + MAF_KEY:
            if need not in full:
                sys.exit(f"{args.maf}: no {need} column")
        used = [n for n in dict.fromkeys(["FORMAT_FIELDS", "GROUP_FORMAT_VALUES"] + MAF_KEY + SLIM_COLUMNS)
                if n in full]
        col = {n: j for j, n in enumerate(used)}
        idx = [full[n] for n in used]
        rows = []
        for line in fin:
            f = line.rstrip("\n").split("\t")
            rows.append([f[i] for i in idx])
    i_fmt, i_grp = col["FORMAT_FIELDS"], col["GROUP_FORMAT_VALUES"]

    calls_by_row = []
    for r in rows:
        values = r[i_grp].split(" ") if r[i_grp] not in ("", MISSING, "NA") else []
        fields = r[i_fmt].split(":")
        if values and len(values) != len(samples):
            sys.exit(f"{args.maf}: {len(values)} genotypes on a row, {len(samples)} members")
        calls_by_row.append([Call(fields, v) for v in values] if values
                            else [Call([], MISSING) for _ in samples])

    role = {m["role"]: i for i, m in reversed(list(enumerate(members)))}
    facts = []
    if args.mode == "family":
        pi, mi, fi = role.get("proband"), role.get("mother"), role.get("father")
        proband_sex = members[pi]["sex"]
        origin = []
        for r, calls in zip(rows, calls_by_row):
            where = region(r[col["Chromosome"]], int(r[col["Start_Position"]]), proband_sex)
            inh, check = inheritance(where, calls[pi], calls[mi] if mi is not None else None,
                                     calls[fi] if fi is not None else None, args)
            origin.append((where, inh))
            facts.append([inh, check, segregation(calls, members, "yes"),
                          segregation(calls, members, "no")])
        # Compound heterozygosity: the proband's het variants, grouped by gene.
        by_gene = defaultdict(list)
        gene_i = col.get("Hugo_Symbol")
        for k, (r, calls) in enumerate(zip(rows, calls_by_row)):
            p = calls[pi]
            if (gene_i is not None and r[gene_i] not in ("", MISSING) and origin[k][0] == "autosomal"
                    and p.carrier and not p.hom):
                by_gene[r[gene_i]].append(k)
        partners = {}
        for ks in by_gene.values():
            for k in ks:
                trans, other = [], []
                for j in ks:
                    if j == k:
                        continue
                    a, b = origin[k][1], origin[j][1]
                    ((trans if {a, b} == {"maternal", "paternal"} else other)
                     .append(label(rows[j], col)))
                partners[k] = (";".join(trans[:MAX_PARTNERS]) or MISSING,
                               ";".join(other[:MAX_PARTNERS]) or MISSING)
        for k in range(len(rows)):
            facts[k] += list(partners.get(k, (MISSING, MISSING)))
        new_cols = FAMILY_COLUMNS
    else:
        for r, calls in zip(rows, calls_by_row):
            called = [i for i, c in enumerate(calls) if c.called]
            carriers = [i for i in called if calls[i].carrier]
            alleles = sum(len(calls[i].alleles) for i in called)
            alt = sum(sum(a != "0" for a in calls[i].alleles) for i in called)
            facts.append([
                str(len(called)), str(len(carriers)),
                str(sum(not calls[i].hom for i in carriers)), str(sum(calls[i].hom for i in carriers)),
                f"{alt / alleles:.4f}" if alleles else MISSING,
                str(len({members[i]["family"] for i in carriers})),
                str(sum(affected_status(members[i]) == "yes" for i in carriers)),
                str(sum(affected_status(members[i]) == "no" for i in carriers)),
                ",".join(samples[i] for i in carriers[:MAX_CARRIERS_LISTED]) or MISSING])
        new_cols = COHORT_COLUMNS

    keep = [i for i, name in enumerate(header) if name != "GROUP_FORMAT_VALUES"]
    member_cols = [f"{f}_{s}" for s in samples for f in MEMBER_FIELDS] if wide else []
    with open(args.maf, newline="\n") as fin, open(args.output, "w", newline="\n") as fout:
        fin.readline()
        fout.write("\t".join([header[i] for i in keep] + member_cols + new_cols) + "\n")
        for line, calls, fct in zip(fin, calls_by_row, facts):
            r = line.rstrip("\n").split("\t")
            genos = [v for c in calls for v in c.columns()] if wide else []
            fout.write("\t".join([r[i] for i in keep] + genos + fct) + "\n")

    if not wide:
        with gzip.open(args.sidecar, "wt") as side:
            side.write("\t".join(MAF_KEY + ["sample"] + MEMBER_FIELDS) + "\n")
            for r, calls in zip(rows, calls_by_row):
                key = [r[col[k]] for k in MAF_KEY]
                for s, c in zip(samples, calls):
                    if c.carrier:
                        side.write("\t".join(key + [s] + c.columns()) + "\n")

    if args.mode == "cohort" and args.genes:
        write_genes(args, rows, calls_by_row, col, members)

    if args.mode == "family":
        counts = defaultdict(int)
        for f in facts:
            counts[f[0]] += 1
        print(f"{args.output}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())),
              file=sys.stderr)


if __name__ == "__main__":
    main()
