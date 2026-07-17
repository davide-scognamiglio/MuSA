#!/path/to/your/env/bin/python <-- CHANGE WITH YOUR INTERPRETER!
#coding=utf-8

import numpy as np
import pandas as pd
from time import time
import sys
import os
#from scipy.stats import randint as sp_randint
#from sklearn.model_selection import train_test_split
#from sklearn.metrics import accuracy_score
from sklearn.ensemble import RandomForestClassifier
#from sklearn.model_selection import RandomizedSearchCV
from sklearn.externals import joblib
#from sklearn.model_selection import cross_val_score

# files upload
basedir = os.path.dirname(__file__)
rf = joblib.load(f"{basedir}/../Files/RF_model.pkl")
keep = pd.read_csv(f"{basedir}/../Files/variables.txt",sep="\t")
col_fin = pd.read_csv(f"{basedir}/../Files/ordered_cols.txt",sep="\t")

input_RF = pd.read_csv(sys.argv[1], sep="\t", na_values=".")

### fix new variables
#keep.loc[-1] = "Type"
#keep = keep.reset_index(drop=True)

# remove useless columns
data = input_RF[keep["Column"]]
data = data.drop(columns="CLNSIG",axis=1)
data = data.drop(columns=["ExonicFunc.refGene","Func.refGene"],axis=1)
index_na = pd.isnull(data).any(1) # rows for which median value has not been calculated are removed
index_na = index_na[index_na].index.values
data = data.dropna()
# perform one-hot-encoding
data_2 = pd.get_dummies(data)

# order categorical variables to perfrom RF and add those that are not present
toadd=list(set(col_fin["Column"]).difference(data_2.columns))
toadd

for col in toadd:
    data_2[col]=0

data_2 = data_2[col_fin["Column"]]

# make predictions with RF
#predictions= rf.predict(data_2)
probs=rf.predict_proba(data_2)[:,1]

# save new columns to the input data
original_input = pd.read_csv(sys.argv[2], sep="\t", na_values=".") #add predictions and probs to this file with pd

# convert predictions to HPP-P-LPP-LPB-B-HPB
# MuSA patch (2026-07-16). The upstream loop walked `probs` (one entry per row that survived
# dropna()) while incrementing a counter over the FULL input, reinserting at most one "NA" per
# surviving prediction. Two consequences, both reproduced on ClinVar chunks:
#   * adjacent dropped rows -> the counter skips the second, RENOVO_Class comes out short, and
#     `input_RF["RENOVO_Class"] = RENOVO_Class` dies with "Length of values does not match length
#     of index" (ReNOVo then exits after deleting ReNOVo_output/, so the caller's mv also fails);
#   * an isolated dropped row -> no crash, but "NA" was appended AFTER that row's prob, so every
#     PL_score from there to the next dropped row sat one row off. Silent, and worse than the crash.
# `data` keeps its original labels through dropna(), so its index states exactly which rows `probs`
# describes. Assign by label and let the dropped rows keep "NA". Thresholds are unchanged.
def _renovo_class(prob):
    if float(prob) < 0.0092:
        return "HP Benign"
    elif float(prob) >= 0.0092 and float(prob) < 0.235:
        return "IP Benign"
    elif float(prob) >= 0.235 and float(prob) < 0.5:
        return "LP Benign"
    elif float(prob) >= 0.5 and float(prob) < 0.7849:
        return "LP Pathogenic"
    elif float(prob) >= 0.7849 and float(prob) < 0.8890:
        return "IP Pathogenic"
    elif float(prob) >= 0.8890:
        return "HP Pathogenic"
    return "NA"

assert len(probs) == len(data_2.index), "predictions do not match the scored rows"

RENOVO_Class = pd.Series("NA", index=input_RF.index, dtype=object)
final_probs = pd.Series("NA", index=input_RF.index, dtype=object)
RENOVO_Class.loc[data_2.index] = [_renovo_class(p) for p in probs]
final_probs.loc[data_2.index] = list(probs)

input_RF["RENOVO_Class"] = RENOVO_Class
input_RF["PL_score"] = final_probs

# Create a subset of right_df with the key columns + the last two columns
input_RF_subset = input_RF[["Chr", "Start", "End", "Ref", "Alt","RENOVO_Class","PL_score"]]

# Merge using a left join on the five key columns
merged_df = pd.merge(original_input, input_RF_subset, on=["Chr", "Start", "End", "Ref", "Alt"], how="left")

# Replace all NaN with "."
merged_df.fillna(".", inplace=True)

# write table finale
merged_df.to_csv(sys.argv[3], sep = "\t", na_rep = ".", index = False)
