#!/usr/bin/env python3
"""Compare the patient's HPO terms with each variant's gene, using HPO's own release.

    hpo_match.py --maf in.maf --hpo "HP:0001250;Microcephaly" --hpo-dir /data/hpo --output out.maf
    hpo_match.py --resolve patients.tsv --hpo-dir /data/hpo --output resolved.tsv

The patient's terms are ';'-separated HPO codes or exact primary names, in any case and mixed
("HP:0001250;microcephaly"). Codes may also be ','-separated, as before 1.6; a name never is,
since 57 names contain a comma. Obsolete and alternative codes map to their current term. A
synonym is refused (976 synonyms equal another term's primary name) and so is anything not
found, with the closest primary names suggested: a wrong term would silently change the match.
--resolve checks a whole samplesheet at once (patient<TAB>terms per line) and writes the
resolved codes, so a typo stops the run before annotation starts.

Reads the ontology (hp.obo) and the gene and disease annotations of the same release
(genes_to_phenotype.txt, phenotype.hpoa) and appends six columns:

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
  HPO_onset         the age of onset HPO records for each of the gene's diseases, whether or not
                    patient terms were given: "OMIM:619340=Infantile onset (HP:0003593);..."
                    (several onsets of one disease are ","-joined). "." when the gene's diseases
                    have no onset annotated, "unannotated" when HPO links no disease to the gene.

Only terms under Phenotypic abnormality (HP:0000118) are compared: mode of inheritance, onset and
frequency terms describe diseases, not the patient's findings. Obsolete and alternative IDs are
mapped to their current term. Without patient terms the five matching columns are "not_requested",
so a missing comparison is never mistaken for a gene that matched nothing ("none").

HPO_onset is a fact about the disease, not a judgement: onset comes from the disease-level
clinical-course annotations (aspect C, terms under Onset HP:0003674), not from the onset some
annotations give for a single phenotypic feature.
"""

import argparse
import difflib
import math
import re
import sys
from collections import defaultdict

PHENOTYPIC_ABNORMALITY = "HP:0000118"
ONSET = "HP:0003674"
PANEL_MAX_GENES = 1000
MISSING = "."
NOT_REQUESTED = "not_requested"
RANK = {"exact": 3, "narrower": 2, "broader": 1, "none": 0}
MATCH_COLUMNS = ["HPO_match", "HPO_match_score", "HPO_matched_terms", "HPO_best_disease", "HPO_panel"]
COLUMNS = MATCH_COLUMNS + ["HPO_onset"]


# ── ontology ──────────────────────────────────────────────────────────────────────────────────────
class Ontology:
    def __init__(self, obo_path):
        self.name, self.parents, self.alias = {}, defaultdict(set), {}
        self.obsolete, self.by_name, self.synonym_of = set(), {}, {}
        self.version = ""
        term, obsolete, replaced, alts, synonyms, in_term = None, False, None, [], [], False

        def close():
            if term is None:
                return
            if obsolete:
                self.obsolete.add(term)
                if replaced:
                    self.alias[term] = replaced
            else:
                self.by_name[" ".join(self.name.get(term, "").lower().split())] = term
                for syn in synonyms:
                    self.synonym_of.setdefault(" ".join(syn.lower().split()), term)
            for a in alts:
                self.alias[a] = term

        with open(obo_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith("data-version:"):
                    self.version = line.split(":", 1)[1].strip()
                if line.startswith("["):
                    close()
                    term, obsolete, replaced, alts, synonyms = None, False, None, [], []
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
                elif key == "synonym" and '"' in val:
                    synonyms.append(val.split('"')[1])
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


def load_disease_onsets(path, onto):
    """Disease ID -> onset terms, from the disease-level clinical-course annotations."""
    onsets = defaultdict(set)
    with open(path, encoding="utf-8") as fh:
        header = None
        for line in fh:
            if line.startswith("#"):
                continue
            r = line.rstrip("\n").split("\t")
            if header is None:
                header = {c: i for i, c in enumerate(r)}
                continue
            if r[header["aspect"]] != "C" or r[header["qualifier"]] == "NOT":
                continue
            term = onto.resolve(r[header["hpo_id"]])
            if term and term != ONSET and ONSET in onto.ancestors(term):
                onsets[r[header["database_id"]]].add(term)
    return onsets


def onset_column(gene, gene_diseases, disease_onsets, onto):
    diseases = gene_diseases.get(gene)
    if not diseases:
        return "unannotated"
    parts = [f"{d}=" + ",".join(onto.label(t) for t in sorted(disease_onsets[d]))
             for d in sorted(diseases) if disease_onsets.get(d)]
    return ";".join(parts) or MISSING


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
CODE = re.compile(r"^HP:\d{7}$")


def split_terms(raw):
    """The samplesheet field as a list of items: ';'-separated; ',' too, but only between codes."""
    items = []
    for part in (raw or "").split(";"):
        part = part.strip()
        pieces = [p.strip() for p in part.split(",")]
        items += pieces if len(pieces) > 1 and all(CODE.match(p.upper()) for p in pieces) else [part]
    return [i for i in items if i and i.upper() not in ("NULL", "NA", ".")]


def resolve_terms(raw, onto):
    """Patient terms as current HPO codes. Returns (terms, notes, errors)."""
    terms, notes, errors = [], [], []
    for item in split_terms(raw):
        if CODE.match(item.upper()):
            code = item.upper()
            cur = onto.resolve(code)
            if cur is None or cur in onto.obsolete:
                errors.append(f"{item}: " + ("obsolete, with no replacement term"
                                             if code in onto.obsolete else
                                             "not an HPO term in this release"))
                continue
            if cur != code:
                notes.append(f"{code} is now {onto.label(cur)}")
        else:
            key = " ".join(item.lower().split())
            cur = onto.by_name.get(key)
            if cur is None:
                syn = onto.synonym_of.get(key)
                if syn:
                    errors.append(f'"{item}": a synonym of {onto.label(syn)}; give that name or '
                                  f"the code")
                else:
                    close = difflib.get_close_matches(key, onto.by_name, n=3, cutoff=0.75)
                    errors.append(f'"{item}": no HPO term has this name'
                                  + (f"; closest: {', '.join(onto.label(onto.by_name[c]) for c in close)}"
                                     if close else ""))
                continue
            notes.append(f'"{item}" is {onto.label(cur)}')
        if not onto.is_phenotype(cur):
            notes.append(f"{onto.label(cur)} is not under Phenotypic abnormality; ignored")
        elif cur not in terms:
            terms.append(cur)
    return terms, notes, errors


def resolve_samplesheet(path, onto, output):
    """--resolve: every patient's terms checked at once, resolved codes written out."""
    failed = False
    with open(path, encoding="utf-8") as fin, open(output, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            patient, _, raw = line.rstrip("\n").partition("\t")
            terms, notes, errors = resolve_terms(raw, onto)
            for n in notes:
                print(f"{patient}: {n}", file=sys.stderr)
            for e in errors:
                print(f"{patient}: ERROR {e}", file=sys.stderr)
            failed |= bool(errors)
            fout.write(f"{patient}\t{';'.join(terms)}\n")
    if failed:
        sys.exit(f"Samplesheet HPO terms that cannot be used (HPO {onto.version}); give each as an "
                 "HP: code or as its exact primary name.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--maf")
    mode.add_argument("--resolve", metavar="TSV", help="patient<TAB>terms per line")
    ap.add_argument("--hpo", default="", help="the patient's HPO terms (codes or names), ';'-separated")
    ap.add_argument("--hpo-dir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    obo = f"{args.hpo_dir}/hp.obo"
    try:
        onto = Ontology(obo)
    except FileNotFoundError:
        sys.exit(f"{obo} not found: this data directory predates HPO support. Run "
                 "`--workflow setup --update_db_only true` once to add the HPO files.")
    if args.resolve:
        resolve_samplesheet(args.resolve, onto, args.output)
        return
    gene_terms, gene_diseases, by_id = load_gene_annotations(
        f"{args.hpo_dir}/genes_to_phenotype.txt", onto)
    disease_onsets = load_disease_onsets(f"{args.hpo_dir}/phenotype.hpoa", onto)

    raw = (args.hpo or "").strip()
    if raw.upper() in ("", "NULL", "NA", "."):
        patient, notes = [], []
        print("HPO: no patient terms in the samplesheet", file=sys.stderr)
    else:
        patient, notes, errors = resolve_terms(raw, onto)
        if errors:
            sys.exit("HPO terms that cannot be used: " + "; ".join(errors))
        print(f"HPO {onto.version}: {len(patient)} patient term(s) "
              f"{', '.join(onto.label(p) for p in patient) or '(none)'}", file=sys.stderr)
        for n in notes:
            print(f"  {n}", file=sys.stderr)

    with open(args.maf, encoding="utf-8", newline="\n") as fin, \
            open(args.output, "w", encoding="utf-8", newline="\n") as fout:
        header = fin.readline().rstrip("\n").split("\t")
        fout.write("\t".join(header + COLUMNS) + "\n")

        m = None
        if patient:
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
                match = (gene_columns(gene, gene_terms, gene_diseases, disease_names,
                                      disease_terms, m)
                         if m else [NOT_REQUESTED] * len(MATCH_COLUMNS))
                cache[gene] = match + [onset_column(gene, gene_diseases, disease_onsets, onto)]
            counts[cache[gene][0]] += 1
            fout.write("\t".join(r + cache[gene]) + "\n")
        if m:
            print("  variants by HPO match: "
                  + ", ".join(f"{k} {counts[k]}" for k in
                              ("exact", "narrower", "broader", "none", "unannotated") if counts[k]),
                  file=sys.stderr)


if __name__ == "__main__":
    main()
