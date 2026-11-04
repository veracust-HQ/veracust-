from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

REQUIRED={"path","label","speaker_id","generator","split","source","license"}
ALLOWED_SPLITS={"train","validation","test"}

def validate(path:Path)->int:
    frame=pd.read_csv(path)
    missing=REQUIRED-set(frame.columns)
    if missing: raise ValueError(f"Missing columns: {sorted(missing)}")
    errors=[]
    if frame[list(REQUIRED)].isna().any().any(): errors.append("Required fields contain blank values.")
    if not set(frame["label"].unique()).issubset({0,1}): errors.append("Labels must be 0 (bona fide) or 1 (synthetic).")
    frame["split"]=frame["split"].astype(str).str.strip().str.lower()
    if not set(frame["split"].unique()).issubset(ALLOWED_SPLITS): errors.append(f"Split must be one of {sorted(ALLOWED_SPLITS)}.")
    if (frame.groupby("speaker_id")["split"].nunique()>1).any(): errors.append("Speaker leakage: speakers must be disjoint across splits.")
    for split,group in frame.groupby("split"):
        if set(group["label"].astype(int).unique())!={0,1}: errors.append(f"Split {split!r} must contain both labels.")
    synthetic=frame[frame["label"].astype(int)==1]
    train_g=set(synthetic.loc[synthetic["split"].isin(["train","validation"]),"generator"].astype(str))
    test_g=set(synthetic.loc[synthetic["split"]=="test","generator"].astype(str))
    overlap=train_g & test_g
    if overlap: errors.append(f"Generator leakage: synthetic test generators also occur in train/validation: {sorted(overlap)}")
    base=path.resolve().parent
    for value in frame["path"].astype(str):
        p=Path(value.strip());p=p if p.is_absolute() else base/p
        if not p.is_file():
            errors.append(f"Audio path does not exist: {p}")
            if len(errors)>=25: break
    if errors:
        for item in errors: print("ERROR:",item)
        return 1
    print(f"Manifest valid: {len(frame)} clips, {frame['speaker_id'].nunique()} speakers.")
    print("Synthetic generator holdout:",", ".join(sorted(test_g)) or "(none)")
    print(frame.groupby(["split","label"]).size().to_string())
    return 0

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("manifest",type=Path)
    raise SystemExit(validate(parser.parse_args().manifest))
