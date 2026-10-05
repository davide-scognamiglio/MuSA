#!/usr/bin/env python3
"""Compare the patient's HPO terms with each variant's gene, using HPO's own release.

    hpo_match.py --maf in.maf --hpo "HP:0001250;HP:0004322" --hpo-dir /data/hpo --output out.maf

Reads the ontology (hp.obo) and the gene and disease annotations of the same release
(genes_to_phenotype.txt, phenotype.hpoa) and appends five columns:

  HPO_match         strongest relation between the patient's terms and the gene's:
                      exact        the gene is annotated to the patient's term
                      narrower     the gene is annotated to a more specific term under it
                      broader      the gene is annotated only to a more general term above it
                      none         the gene has phenotype annotations, none of them related
                      unannotated  HPO has no phenotype annotation for the gene
  HPO_match_score   0-1 similarity: for each patient term, the information content of the most
                    informative term it shares with the gene's annotations, divided by the
                    patient term's own; averaged over the patient's terms. 1 means every term is
                    matched exactly or by a narrower one; a partial value means only more
                    general ancestors are shared.
  HPO_matched_terms each related patient term with how it matched, e.g.
                    "Seizure (HP:0001250): narrower, Epileptic spasm (HP:0011097)"
  HPO_best_disease  the gene's disease (OMIM / Orphanet / DECIPHER) whose phenotype matches the
                    patient best, with its score
  HPO_panel         yes / no: the gene matches, exactly or narrower, a patient term specific
                    enough to define a panel (annotated to fewer than PANEL_MAX_GENES genes,
                    the same cut-off the former online lookup used). "." when no patient term
                    is that specific, so FILTER_VARIANTS applies no HPO filter.

Only terms under Phenotypic abnormality (HP:0000118) are compared: mode of inheritance, onset and
frequency terms describe diseases, not the patient's findings. Obsolete and alternative IDs are
mapped to their current term. Without patient terms every column is ".".
"""

import argparse
import math
import sys
from collections import defaultdict

PHENOTYPIC_ABNORMALITY = "HP:0000118"
PANEL_MAX_GENES = 1000
MISSING = "."
RANK = {"exact": 3, "narrower": 2, "broader": 1, "none": 0}
COLUMNS = ["HPO_match", "HPO_match_score", "HPO_matched_terms", "HPO_best_disease", "HPO_panel"]


# ── ontology ──────────────────────────────────────────────────────────────────────────────────────
class Ontology:
    def __init__(self, obo_path):
        self.name, self.parents, self.alias = {}, defaultdict(set), {}
        self.version = ""
        term, obsolete, replaced, alts, in_term = None, False, None, [], False

        def close():
            if term is None:
                return
            if obsolete:
                if replaced:
                    self.alias[term] = replaced
            for a in alts:
                self.alias[a] = term

        with open(obo_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("data-version:"):
                    self.version = line.split(":", 1)[1].strip()
                if line.startswith("["):
                    close()
                    term, obsolete, replaced, alts = None, False, None, []
                    in_term = line == "[Term]"
                    continue
                if not in_term or ":" not in line:
                    continue
                key, val = line.split(":", 1)
                val = val.strip()
                if key == "id":
                    term = val
                elif key == "name":
                    self.name[term] = val
                elif key == "is_a":
                    self.parents[term].add(val.split("!")[0].strip())
                elif key == "alt_id":
                    alts.append(val)
                elif key == "is_obsolete" and val == "true":
                    obsolete = True
                elif key == "replaced_by":
                    replaced = val
        close()
        self._anc = {}

    def resolve(self, term):
        seen = set()
        while term in self.alias and term not in seen:
            seen.add(term)
            term = self.alias[term]
        return term if term in self.name else None

    def ancestors(self, term):
        """The term and every term above it."""
        if term not in self._anc:
            out, stack = {term}, [term]
            while stack:
                for p in self.parents.get(stack.pop(), ()):
                    if p not in out:
                        out.add(p)
                        stack.append(p)
            self._anc[term] = frozenset(out)
        return self._anc[term]

    def is_phenotype(self, term):
        return PHENOTYPIC_ABNORMALITY in self.ancestors(term)

    def label(self, term):
        return f"{self.name.get(term, term)} ({term})"


# ── annotations ───────────────────────────────────────────────────────────────────────────────────
def load_gene_annotations(path, onto):
    """Gene symbol and NCBI id -> phenotype terms, and gene -> disease IDs."""
    terms, diseases, by_id = defaultdict(set), defaultdict(set), {}
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        col = {c: i for i, c in enumerate(header)}
        for line in fh:
            r = line.rstrip("\n").split("\t")
            gene = r[col["gene_symbol"]]
            by_id[r[col["ncbi_gene_id"]]] = gene
            term = onto.resolve(r[col["hpo_id"]])
            if term and onto.is_phenotype(term):
                terms[gene].add(term)
            disease = r[col["disease_id"]]
            if disease and disease != "-":
                diseases[gene].add(disease)
    return terms, diseases, by_id


def load_disease_annotations(path, onto):
    """Disease ID -> (name, phenotype terms); NOT-qualified annotations are left out."""
    names, terms = {}, defaultdict(set)
    with open(path, encoding="utf-8") as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                continue
            r = line.rstrip("\n").split("\t")
            if header is None:
                header = {c: i for i, c in enumerate(r)}
                continue
            if r[header["aspect"]] != "P" or r[header["qualifier"]] == "NOT":
                continue
            disease = r[header["database_id"]]
            names[disease] = r[header["disease_name"]]
            term = onto.resolve(r[header["hpo_id"]])
            if term:
                terms[disease].add(term)
    return names, terms


def information_content(gene_terms, onto):
    """IC(t) = -ln(fraction of annotated genes carrying t or a descendant of t)."""
    count = defaultdict(int)
    for annotated in gene_terms.values():
        for t in set().union(*(onto.ancestors(x) for x in annotated)):
            count[t] += 1
    n = len(gene_terms)
    ic = {t: -math.log(c / n) for t, c in count.items()}
    return ic, count, -math.log(1 / n)


# ── matching ──────────────────────────────────────────────────────────────────────────────────────
class Matcher:
    def __init__(self, onto, patient, ic, ic_max, gene_count):
        self.onto, self.patient, self.ic, self.ic_max = onto, patient, ic, ic_max
        # Children of Phenotypic abnormality are organ systems ("Abnormality of the nervous
        # system"): sharing one says almost nothing, so they never count as a "broader" match.
        self.too_general = {PHENOTYPIC_ABNORMALITY} | {
            t for t, ps in onto.parents.items() if PHENOTYPIC_ABNORMALITY in ps}
        self.panel_terms = {p for p in patient if gene_count.get(p, 0) < PANEL_MAX_GENES}

    def _ic(self, t):
        return self.ic.get(t, self.ic_max)

    def score(self, annotated):
        """Mean over patient terms of IC(most informative shared ancestor) / IC(patient term)."""
        covered = set().union(*(self.onto.ancestors(t) for t in annotated)) if annotated else set()
        vals = []
        for p in self.patient:
            own = self._ic(p)
            if own <= 0:
                continue
            shared = self.onto.ancestors(p) & covered
            best = max((self._ic(a) for a in shared), default=0.0)
            vals.append(min(1.0, best / own))
        return sum(vals) / len(vals) if vals else 0.0, covered

    def relations(self, annotated, covered):
        """Per patient term: (relation, the gene term that shows it)."""
        out = {}
        for p in self.patient:
            if p in annotated:
                out[p] = ("exact", p)
            elif p in covered:
                below = [t for t in annotated if p in self.onto.ancestors(t)]
                out[p] = ("narrower", max(below, key=self._ic))
            else:
                above = [t for t in annotated
                         if t in self.onto.ancestors(p) and t not in self.too_general]
                out[p] = ("broader", max(above, key=self._ic)) if above else ("none", None)
        return out


def gene_columns(gene, gene_terms, gene_diseases, disease_names, disease_terms, m):
    annotated = gene_terms.get(gene)
    if not annotated:
        return ["unannotated", MISSING, MISSING, MISSING, "no" if m.panel_terms else MISSING]
    score, covered = m.score(annotated)
    rel = m.relations(annotated, covered)
    best = max((r for r, _ in rel.values()), key=RANK.get, default="none")
    matched = []
    for p, (r, t) in rel.items():
        if r == "exact":
            matched.append(f"{m.onto.label(p)}: exact")
        elif r != "none":
            matched.append(f"{m.onto.label(p)}: {r}, {m.onto.label(t)}")
    disease, d_score = None, 0.0
    for d in sorted(gene_diseases.get(gene, ())):
        if disease_terms.get(d):
            s, _ = m.score(disease_terms[d])
            if s > d_score:
                disease, d_score = d, s
    panel = MISSING
    if m.panel_terms:
        panel = "yes" if any(rel[p][0] in ("exact", "narrower") for p in m.panel_terms) else "no"
    return [
        best,
        f"{score:.3f}",
        "; ".join(matched) or MISSING,
        f"{disease} {disease_names.get(disease, '')} ({d_score:.3f})".replace("  ", " ")
        if disease else MISSING,
        panel,
    ]


# ── main ──────────────────────────────────────────────────────────────────────────────────────────
def parse_patient_terms(raw, onto):
    terms, notes = [], []
    for t in (raw or "").replace(",", ";").split(";"):
        t = t.strip().upper()
        if not t or t in ("NULL", "NA", "."):
            continue
        cur = onto.resolve(t)
        if cur is None:
            notes.append(f"{t} is not an HPO term in this release; ignored")
        elif not onto.is_phenotype(cur):
            notes.append(f"{t} ({onto.name[cur]}) is not under Phenotypic abnormality; ignored")
        else:
            if cur != t:
                notes.append(f"{t} is now {cur} ({onto.name[cur]})")
            if cur not in terms:
                terms.append(cur)
    return terms, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--maf", required=True)
    ap.add_argument("--hpo", default="", help="the patient's HPO terms, ';'-separated")
    ap.add_argument("--hpo-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    raw = (args.hpo or "").strip()
    if raw.upper() in ("", "NULL", "NA", "."):
        patient, notes = [], []
        print("HPO: no patient terms in the samplesheet", file=sys.stderr)
    else:
        obo = f"{args.hpo_dir}/hp.obo"
        try:
            onto = Ontology(obo)
        except FileNotFoundError:
            sys.exit(f"{obo} not found: this data directory predates HPO support. Run "
                     "`--workflow setup --update_db_only true` once to add the HPO files.")
        patient, notes = parse_patient_terms(raw, onto)
        print(f"HPO {onto.version}: {len(patient)} patient term(s) "
              f"{', '.join(onto.label(p) for p in patient) or '(none)'}", file=sys.stderr)
        for n in notes:
            print(f"  {n}", file=sys.stderr)

    with open(args.maf, encoding="utf-8", newline="\n") as fin, \
            open(args.output, "w", encoding="utf-8", newline="\n") as fout:
        header = fin.readline().rstrip("\n").split("\t")
        fout.write("\t".join(header + COLUMNS) + "\n")
        if not patient:
            for line in fin:
                fout.write(line.rstrip("\n") + "\t" + "\t".join([MISSING] * len(COLUMNS)) + "\n")
            return

        gene_terms, gene_diseases, by_id = load_gene_annotations(
            f"{args.hpo_dir}/genes_to_phenotype.txt", onto)
        disease_names, disease_terms = load_disease_annotations(
            f"{args.hpo_dir}/phenotype.hpoa", onto)
        ic, gene_count, ic_max = information_content(gene_terms, onto)
        m = Matcher(onto, patient, ic, ic_max, gene_count)
        skipped = sorted(set(patient) - m.panel_terms)
        if skipped:
            print(f"  too general to filter on (>= {PANEL_MAX_GENES} genes): "
                  f"{', '.join(onto.label(p) for p in skipped)}", file=sys.stderr)

        col = {c: i for i, c in enumerate(header)}
        sym_i, id_i = col.get("Hugo_Symbol"), col.get("Entrez_gene_id")
        cache, counts = {}, defaultdict(int)
        for line in fin:
            r = line.rstrip("\n").split("\t")
            # The NCBI gene id is the stable key; the symbol is the fallback.
            gene = by_id.get(r[id_i]) if id_i is not None and id_i < len(r) else None
            if gene is None and sym_i is not None and sym_i < len(r):
                gene = r[sym_i]
            if gene not in cache:
                cache[gene] = gene_columns(gene, gene_terms, gene_diseases, disease_names,
                                           disease_terms, m)
            counts[cache[gene][0]] += 1
            fout.write("\t".join(r + cache[gene]) + "\n")
        print("  variants by HPO match: "
              + ", ".join(f"{k} {counts[k]}" for k in
                          ("exact", "narrower", "broader", "none", "unannotated") if counts[k]),
              file=sys.stderr)


if __name__ == "__main__":
    main()
