---
title: The MAF in Python
summary: Load MuSA's raw MAF in pandas, filter it, and build a feature table for a model.
order: 2
---

# The MAF in Python

MuSA's raw MAF is a plain tab-separated table: one row per variant, one transcript per variant
(MANE Select), one column per annotation. 168 columns in basic mode, 887 in extended mode. The
output below comes from NA12878 in basic mode (22,572 variants).

## Load it

```python
import pandas as pd

maf = pd.read_csv("results/<date>/NA12878/NA12878.raw.maf", sep="\t", low_memory=False)
maf.shape
# (22572, 168)
```

`low_memory=False` lets pandas read each column's type from the whole file, which matters for
sparse columns.

## Look around

```python
maf["IMPACT"].value_counts()
# MODERATE    11652
# LOW         10307
# HIGH          560
# MODIFIER       53

maf["HPO_match"].value_counts()   # how each gene matched the patient's HPO terms
# unannotated    15300
# none            4434
# exact           2159
# narrower         426
# broader          253
```

`Consequence` holds every consequence of the variant on its transcript, comma-separated:

```python
maf["Consequence"].str.split(",").str[0].value_counts().head(3)
# missense_variant         11354
# synonymous_variant        9937
# splice_region_variant      290
```

## Filter

ClinVar pathogenic or likely pathogenic:

```python
plp = maf[maf["CLNSIG"].isin(["Pathogenic", "Likely_pathogenic", "Pathogenic/Likely_pathogenic"])]
plp[["Hugo_Symbol", "HGVSp_VEP", "CLNSIG", "gnomADe_AF", "HPO_match"]]
#       Hugo_Symbol    HGVSp_VEP      CLNSIG  gnomADe_AF HPO_match
# 3682          PAH  p.Tyr414Cys  Pathogenic   0.0003646     exact
# 18739         PLG   p.Lys38Glu  Pathogenic    0.005207      none
```

Rare variants (gnomAD exomes below 0.1%; absent counts as rare):

```python
af = pd.to_numeric(maf["gnomADe_AF"], errors="coerce").fillna(0)
rare = maf[af < 0.001]
len(rare)
# 589
```

## A feature table for a model

Score columns are numbers, or empty when the source has nothing for that variant. Pick the
columns, coerce them to numbers, and decide how to treat missing values explicitly:

```python
key = ["Chromosome", "Start_Position", "Reference_Allele", "Tumor_Seq_Allele2"]
features = ["gnomADe_AF", "MAX_AF", "HPO_match_score"]   # extended mode adds REVEL_score,
                                                         # AlphaMissense_score, CADD_PHRED, ...
X = maf[key + features].copy()
X[features] = X[features].apply(pd.to_numeric, errors="coerce")
X["gnomADe_AF_missing"] = X["gnomADe_AF"].isna()
X = X.fillna({"gnomADe_AF": 0, "MAX_AF": 0})
X.set_index(key).to_parquet("NA12878.features.parquet")   # needs pyarrow
```

The four key columns identify a variant across samples and runs, so tables from many patients
can be stacked or joined on them.

## Know where each column comes from

Every column has an owner in MuSA's source catalogue: [Sources](../../docs/sources/) lists each
source, its version and its columns. Cite the sources you use; `CITATIONS.md` in the repository
has the references.
