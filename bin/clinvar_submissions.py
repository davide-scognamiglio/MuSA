#!/usr/bin/env python3
"""What ClinVar submitters wrote about a variant: ACMG codes they name and functional evidence.

    clinvar_submissions.py build    submission_summary_2026-07.txt.gz clinvar_submissions.tsv.gz
    clinvar_submissions.py annotate --maf in.maf --index clinvar_submissions.tsv.gz --output out.maf

ClinVar's submission_summary carries every submitted record (SCV) with the submitter's free-text
comment. Laboratories often list the ACMG codes they applied ("Criteria applied: PVS1,PS3,PM2") and
describe functional studies ("In vitro functional studies demonstrated loss of kinase activity
(PMID: 12345678)"). This turns that text into facts per ClinVar variant. It decides nothing: a
submission naming PS3 is reported as such, not as "PS3 is met".

Expert-panel and practice-guideline submissions (and any ClinGen submitter) are kept apart: they
never enter the counts and appear only in ClinVar_EP_codes. On the ClinGen Evidence Repository
benchmark the panels' own submissions are the answer key, so a consumer must be able to leave them
out. Flagged submissions (ClinVar marks them as outdated or in error) and records without a
germline classification are skipped.

Columns added (ClinVar_VariationID is the join key; "." when the variant has no ClinVar record):
  ClinVar_SCV_n                 submissions counted (germline, not flagged, not expert panel)
  ClinVar_SCV_PS3_n             of those, how many name PS3 in their comment (any strength)
  ClinVar_SCV_PS3_codes         the PS3 codes as written, with counts: "PS3:2;PS3_Moderate:1"
  ClinVar_SCV_BS3_n             the same for BS3
  ClinVar_SCV_BS3_codes
  ClinVar_SCV_func_n            submissions with a sentence describing a functional study
  ClinVar_SCV_func_abnormal_n   ... whose study sentence reports an effect (reduced, abolished ...)
  ClinVar_SCV_func_normal_n     ... whose study sentence reports no effect (similar to wild type ...)
  ClinVar_SCV_func_absent_n     submissions stating that no functional evidence exists
  ClinVar_SCV_func_pmids        PMIDs cited inside the functional-study sentences
  ClinVar_SCV_func_quote        the shortest functional-study sentence, "[submitter]" appended
  ClinVar_EP_codes              each expert-panel submission's classification and ACMG codes:
                                "Pathogenic: PS3_Moderate,PM2_Supporting,PP3 [ClinGen PAH VCEP]"

The statement classifier is a fixed set of rules, not a model (see FUNCTIONAL, ABSENT, NORMAL and
ABNORMAL below). A statement counts as a functional study only when it uses assay vocabulary and is
not a computational prediction; "no functional studies have been reported" counts as absent, not as
a study. A study statement reporting both an effect and no effect, or neither, is counted in
func_n only. Hand audit of 100 statements: see docs/output.md.
"""

import argparse
import gzip
import os
import re
import sys
from collections import Counter

# submission_summary.txt.gz columns used, checked against the header at build time.
COLUMNS = {
    "#VariationID": 0, "ClinicalSignificance": 1, "Description": 3, "ReviewStatus": 6,
    "Submitter": 9, "ExplanationOfInterpretation": 12,
}
EXPERT_STATUS = {"reviewed by expert panel", "practice guideline"}

# An ACMG code with an optional strength suffix, in the spellings submitters use:
# PS3, PS3_Moderate, PS3_mod, PS3-supporting, PS3 (strong), PS3_P, BS3_Supp ...
CODE = re.compile(
    r"\b(PVS1|PS[1-4]|PM[1-6]|PP[1-5]|BA1|BS[1-4]|BP[1-7])"
    r"(?:[ _-]?\(?(very[ _-]?strong|strong|moderate|mod|supporting|supp?|stand[ _-]?alone|"
    r"vs|s|m|p)\)?)?(?![A-Za-z0-9])",
    re.I)
STRENGTH = {"verystrong": "VeryStrong", "vs": "VeryStrong", "strong": "Strong", "s": "Strong",
            "moderate": "Moderate", "mod": "Moderate", "m": "Moderate", "supporting": "Supporting",
            "supp": "Supporting", "sup": "Supporting", "p": "Supporting",
            "standalone": "StandAlone"}

# Statement boundary: end punctuation followed by a capital letter or an opening bracket, or a
# semicolon followed by a capital letter. Several laboratories write their whole comment as
# ";"-joined statements ("Not observed in gnomAD; In silico analysis supports ...; Published
# functional studies demonstrate ..."), and the in silico and functional halves must be read apart.
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\[])|;\s+(?=[A-Z])")
FUNCTIONAL = re.compile(
    r"\b(functional (?:stud\w*|assays?|analys[ie]s|evidence|data|characteri[sz]\w*|experiments?|"
    r"testing|investigations?)|experimental (?:stud\w*|evidence|data|assays?)|in vitro|in vivo|"
    r"assay(?!ed region)\w*|enzym\w* activit\w*|residual activit\w*|kinase activit\w*|minigene|"
    r"luciferase|reporter (?:gene|assay)|transfect\w*|knock-?in|mouse model|animal model|"
    r"western blot|immunoblot|patch[- ]clamp|electrophysiolog\w*|RT-PCR|RNA (?:analys[ie]s|stud\w*)|"
    r"splicing (?:assay|analys[ie]s|stud\w*)|deep mutational scanning|saturation genome editing|"
    r"multiplex(?:ed)? assay\w*|MAVE)\b",
    re.I)
PREDICTION = re.compile(r"\b(in silico|computational|algorithm\w*|prediction\w*|predicted|predicts?)\b",
                        re.I)
EXPERIMENT = re.compile(r"\b(in vitro|in vivo|assay\w*|experimental|functional stud\w*|minigene)\b", re.I)
ABSENT = re.compile(
    r"\bno (?:published |reported |available |direct )?(?:functional|experimental)\b|"
    r"\b(?:functional|experimental) (?:stud\w*|evidence|data|assays?|analys[ie]s|characteri[sz]\w*)"
    r"(?:\s+\S+){0,4}?\s+(?:not been|has not|have not|are not|is not|were not|was not|lacking|unavailable|"
    r"not available|not yet|absent|limited|unknown)\b|"
    r"\b(?:not|never|yet to)(?: been| be)? confirmed (?:by|in|with|through) (?:published )?"
    r"(?:functional|RNA|experimental|in vitro)|"
    r"\b(?:lack|absence) of (?:published )?(?:\S+/)?(?:functional|experimental)|"
    r"\b(?:not|nor) (?:been )?(?:evaluated|assessed|tested|studied|investigated|characteri[sz]ed) "
    r"(?:for|in|by|with) (?:its )?(?:functional|in vitro|in vivo|experimental)|"
    r"\bhas not been (?:functionally|experimentally) (?:characteri|stud|assess|test|evaluat|investigat)\w*|"
    r"\bfunctional (?:consequence|impact|effect|significance|relevance)s?(?:\s+\S+){0,4}?\s+"
    r"(?:is|are|remains?) (?:unknown|unclear|not known|uncertain)\b",
    re.I)
NORMAL = re.compile(
    r"\b(?:no|not|did not|does not|do not|without|neither|nor)\s+(?:\S+\s+){0,3}?(?:significant(?:ly)?\s+|"
    r"substantial(?:ly)?\s+|detectable\s+|measurable\s+)?(?:effect|impact\w*|affect\w*|alter\w*|chang\w*|"
    r"reduc\w*|impair\w*|differ\w*|disrupt\w*|decreas\w*|abnormal\w*|damag\w*|deleterious)|"
    r"\bno evidence (?:that|of)\b(?:\s+\S+){0,6}|"
    r"\b(?:similar|comparable|equivalent|identical) to (?:that of )?(?:the )?wild[- ]?type|"
    r"\bfunctionally (?:normal|neutral)|\bneutral (?:effect|in )|\bwild[- ]?type[- ]like|"
    r"\bfully functional|\b(?:has|had|have|showed|shows|with|retain\w*) (?:normal|full) "
    r"(?:function|activit\w*|splicing)",
    re.I)
# "affect", "impact" and "alter" count only as verbs with a molecular object: "alteration" names the
# variant, "affected individuals" are patients, "evaluating an impact" reports no result.
EFFECT_OBJECT = (r"(?:\S+ ){0,3}(?:function\w*|activit\w*|splicing|expression|stability|binding|"
                 r"folding|localization|level\w*|currents?|conductance|structure|processing|"
                 r"transport\w*|secretion|signal\w*|trafficking|propert\w*|probability|interaction\w*)")
ABNORMAL = re.compile(
    r"\b(loss[- ]of[- ]function|gain[- ]of[- ]function|dominant[- ]negative|"
    r"(?:reduc|decreas|impair|abolish|abrogat|disrupt|diminish|lower|attenuat|destabili[sz]|"
    r"interfer)\w*|(?<!an )(?<!the )(?<!any )(?:affect|impact|alter)(?:s|ed|ing)?\s+(?:on\s+)?" + EFFECT_OBJECT + r"|"
    r"partial(?:ly)?|defective|deficien\w*|loss (?:of|in)|lack of|no detectable|undetectable|absent|"
    r"abnormal\w*|aberrant\w*|(?<!-)damaging|deleterious|exon skipping|skipping of exon|"
    r"retention of intron|intron retention|nonfunctional|non-functional|null)\b",
    re.I)
PMID = re.compile(r"\bPMIDs?\s*:?\s*((?:\d{6,9}[\s,;and]*)+)", re.I)
DIGITS = re.compile(r"\d{6,9}")
QUOTE_MIN, QUOTE_MAX = 40, 400

INDEX_HEADER = ["variation_id", "scv_n", "ps3_n", "ps3_codes", "bs3_n", "bs3_codes", "func_n",
                "func_abnormal_n", "func_normal_n", "func_absent_n", "func_pmids", "func_quote",
                "ep_codes"]
MAF_COLUMNS = ["ClinVar_SCV_n", "ClinVar_SCV_PS3_n", "ClinVar_SCV_PS3_codes", "ClinVar_SCV_BS3_n",
               "ClinVar_SCV_BS3_codes", "ClinVar_SCV_func_n", "ClinVar_SCV_func_abnormal_n",
               "ClinVar_SCV_func_normal_n", "ClinVar_SCV_func_absent_n", "ClinVar_SCV_func_pmids",
               "ClinVar_SCV_func_quote", "ClinVar_EP_codes"]


def clean(text):
    text = (text or "").strip()
    return "" if text in ("-", "na", "not provided") else re.sub(r"\s+", " ", text)


def codes(text):
    """Every ACMG code in the text, normalised: "PS3", "PS3_Moderate", ... in order of appearance."""
    out = []
    for m in CODE.finditer(text):
        code = m.group(1).upper()
        s = m.group(2)
        if s:
            s = STRENGTH.get(re.sub(r"[ _-]", "", s.lower()))
        name = f"{code}_{s}" if s else code
        if name not in out:
            out.append(name)
    return out


def direction(sentence):
    """"normal", "abnormal", "mixed" or None for one functional-study statement.

    A no-effect phrase ("did not reduce activity") contains an effect word, so the no-effect
    matches are cut out before looking for an effect; both left over means mixed results.
    """
    normal = bool(NORMAL.search(sentence))
    rest = NORMAL.sub(" ", sentence)
    abnormal = bool(ABNORMAL.search(rest))
    if normal and abnormal:
        return "mixed"
    return "normal" if normal else "abnormal" if abnormal else None


def classify(text):
    """(functional statements, set of directions, absent statement?) for one comment."""
    sentences, directions, absent = [], set(), False
    for sentence in SENTENCE.split(text):
        if ABSENT.search(sentence):
            absent = True
            continue
        if not FUNCTIONAL.search(sentence):
            continue
        # A prediction statement that only borrows the vocabulary ("predicted to affect protein
        # function") is not a study, unless it also names a real experiment.
        if PREDICTION.search(sentence) and not EXPERIMENT.search(sentence):
            continue
        sentences.append(sentence)
        d = direction(sentence)
        if d in ("normal", "abnormal"):
            directions.add(d)
    return sentences, directions, absent


def pmids(sentences):
    found = []
    for s in sentences:
        for m in PMID.finditer(s):
            for d in DIGITS.findall(m.group(1)):
                if d not in found:
                    found.append(d)
    return found


# ── build ─────────────────────────────────────────────────────────────────────────────────────────
class Variant:
    __slots__ = ("scv", "ps3", "bs3", "ps3_codes", "bs3_codes", "func", "abnormal", "normal",
                 "absent", "pmids", "quote", "ep")

    def __init__(self):
        self.scv = self.ps3 = self.bs3 = self.func = self.abnormal = self.normal = self.absent = 0
        self.ps3_codes, self.bs3_codes = Counter(), Counter()
        self.pmids, self.quote, self.ep = [], None, []


def build(args):
    variants = {}
    n_ep = n_skipped = 0
    with gzip.open(args.summary, "rt", encoding="utf-8", errors="replace") as fh:
        header = None
        for line in fh:
            # The column header; the description lines above it also start with "#VariationID".
            if line.startswith("#VariationID\t"):
                header = line.rstrip("\n").split("\t")
                for name, i in COLUMNS.items():
                    if i >= len(header) or header[i] != name:
                        sys.exit(f"submission_summary column {i} is not '{name}': the format changed")
                continue
            if line.startswith("#"):
                continue
            if header is None:
                sys.exit("submission_summary: no #VariationID header line")
            f = line.rstrip("\n").split("\t")
            if len(f) <= COLUMNS["ExplanationOfInterpretation"]:
                continue
            sig = f[COLUMNS["ClinicalSignificance"]].strip()
            status = f[COLUMNS["ReviewStatus"]].strip().lower()
            if sig in ("", "-") or status == "flagged submission":
                n_skipped += 1
                continue
            text = " ".join(t for t in (clean(f[COLUMNS["Description"]]),
                                        clean(f[COLUMNS["ExplanationOfInterpretation"]])) if t)
            submitter = f[COLUMNS["Submitter"]].strip()
            v = variants.setdefault(f[COLUMNS["#VariationID"]], Variant())
            if status in EXPERT_STATUS or submitter.startswith("ClinGen"):
                n_ep += 1
                listed = codes(text)
                v.ep.append(f"{sig}: {','.join(listed) if listed else '-'} [{submitter}]")
                continue
            v.scv += 1
            if not text:
                continue
            listed = codes(text)
            ps3 = [c for c in listed if c.startswith("PS3")]
            bs3 = [c for c in listed if c.startswith("BS3")]
            if ps3:
                v.ps3 += 1
                v.ps3_codes.update(ps3)
            if bs3:
                v.bs3 += 1
                v.bs3_codes.update(bs3)
            sentences, directions, absent = classify(text)
            v.absent += absent
            if sentences:
                v.func += 1
                v.abnormal += "abnormal" in directions
                v.normal += "normal" in directions
                for p in pmids(sentences):
                    if p not in v.pmids:
                        v.pmids.append(p)
                for s in sentences:
                    if QUOTE_MIN <= len(s) <= QUOTE_MAX and (v.quote is None or len(s) < len(v.quote[0])):
                        v.quote = (s, submitter)

    def joined(counter):
        return ";".join(f"{c}:{n}" for c, n in sorted(counter.items())) or "."

    with gzip.open(args.output, "wt", newline="") as out:
        out.write("\t".join(INDEX_HEADER) + "\n")
        for vid in sorted(variants, key=lambda x: int(x) if x.isdigit() else 0):
            v = variants[vid]
            quote = f"{v.quote[0]} [{v.quote[1]}]" if v.quote else "."
            row = [vid, v.scv, v.ps3, joined(v.ps3_codes), v.bs3, joined(v.bs3_codes), v.func,
                   v.abnormal, v.normal, v.absent, ",".join(v.pmids) or ".", quote,
                   "; ".join(v.ep) or "."]
            out.write("\t".join(re.sub(r"[\t\r\n]", " ", str(x)) for x in row) + "\n")
    with_func = sum(v.func > 0 for v in variants.values())
    print(f"{args.output}: {len(variants)} ClinVar variants, {with_func} with a functional-study "
          f"sentence, {n_ep} expert-panel submissions kept apart, {n_skipped} skipped "
          "(flagged or no germline classification)")


# ── annotate ──────────────────────────────────────────────────────────────────────────────────────
def annotate(args):
    if not os.path.isfile(args.index):
        sys.exit(f"{args.index} not found: this data directory predates MuSA 1.5's ClinVar "
                 "submission index. Run `--workflow setup --update_db_only true` once to add it.")
    with open(args.maf, newline="\n") as fin:
        header = fin.readline().rstrip("\n").split("\t")
        if "ClinVar_VariationID" not in header:
            sys.exit(f"{args.maf}: no ClinVar_VariationID column")
        vid_i = header.index("ClinVar_VariationID")
        wanted = set()
        for line in fin:
            f = line.rstrip("\n").split("\t")
            wanted.update(x for x in f[vid_i].split(",") if x not in ("", "."))

    # The index has a row for every ClinVar variant; only the MAF's are kept in memory.
    index = {}
    with gzip.open(args.index, "rt") as fh:
        if next(fh).rstrip("\n").split("\t") != INDEX_HEADER:
            sys.exit(f"{args.index}: unexpected header; rebuild it with this MuSA version's setup")
        for line in fh:
            vid, rest = line.rstrip("\n").split("\t", 1)
            if vid in wanted:
                index[vid] = rest.split("\t")

    n_hit = 0
    with open(args.maf, newline="\n") as fin, open(args.output, "w", newline="\n") as fout:
        fin.readline()
        fout.write("\t".join(header + MAF_COLUMNS) + "\n")
        for line in fin:
            f = line.rstrip("\n").split("\t")
            # A multi-allelic ClinVar match can carry several ids; the first one with a record wins.
            row = next((index[x] for x in f[vid_i].split(",") if x in index), None)
            n_hit += row is not None
            fout.write("\t".join(f + (row if row else ["."] * len(MAF_COLUMNS))) + "\n")
    print(f"{args.output}: ClinVar submissions for {n_hit} variants", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("summary")
    b.add_argument("output")
    a = sub.add_parser("annotate")
    a.add_argument("--maf", required=True)
    a.add_argument("--index", required=True)
    a.add_argument("--output", required=True)
    args = ap.parse_args()
    {"build": build, "annotate": annotate}[args.cmd](args)


if __name__ == "__main__":
    main()
