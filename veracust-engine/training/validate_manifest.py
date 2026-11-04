from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

REQUIRED = {"path", "label", "speaker_id", "generator", "split", "source", "license"}
ALLOWED_SPLITS = {"train", "validation", "test"}

def validate(path: Path) -> int:
    frame = pd.read_csv(path)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    errors = []
    if frame[list(REQUIRED)].isna().any().any():
        errors.append("Required manifest fields contain blank values.")
    if not set(frame["label"].unique()).issubset({0, 1}):
        errors.append("Labels must be 0 (bona fide) or 1 (synthetic).")
    if not set(frame["split"].unique()).issubset(ALLOWED_SPLITS):
        errors.append(f"Split must be one of {sorted(ALLOWED_SPLITS)}.")
    speaker_splits = frame.groupby("speaker_id")["split"].nunique()
    if (speaker_splits > 1).any():
        errors.append("Speaker leakage: one or more speakers appear in multiple splits.")
    for split, group in frame.groupby("split"):
        if group["label"].nunique() < 2:
            errors.append(f"Split {split!r} does not contain both classes.")
    for p in frame["path"].astype(str):
        if not Path(p).is_file():
            errors.append(f"Audio path does not exist: {p}")
            if len(errors) > 20:
                break
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print(f"Manifest valid: {len(frame)} rows, {frame['speaker_id'].nunique()} speakers.")
    print(frame.groupby(["split", "label"]).size().to_string())
    return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    raise SystemExit(validate(parser.parse_args().manifest))
