"""Train and honestly evaluate a small fall classifier on the pose features from fall_features.py.

Each sample is a 1.5 s window of per-frame features. A window is a FALL when it ends within 2 s after the annotated fall begins.
Everything else (normal activity, and the parts of a fall clip before or well after the fall) is NOT a fall.

Evaluation is leave-one-subject-out: the model is trained on three people and tested on the fourth, so it is always judged on someone it has
never seen. Clip level: a fall clip is "caught" if any of its windows fires; a normal clip is a "false alarm" if any of its windows fires.

Usage:  python scripts/fall_train.py data/falls/features.csv weights/fall_model.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ppe.fall_model import FEATURES, WINDOW, window_features as _window_features  # the same numbers the live detector uses

def window_features(win: pd.DataFrame) -> list[float]:
    return _window_features(win["torso_angle"], win["aspect"], win["hip_y"], win["head_y"], win["head_hip"], win["height"])

def build(table: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (subject, group, clip), clipdf in table.groupby(["subject", "group", "clip"]):
        clipdf = clipdf[clipdf["valid"] == 1].sort_values("t").reset_index(drop=True)
        start = clipdf["fall_start"].iloc[0] if len(clipdf) and pd.notna(clipdf["fall_start"].iloc[0]) else None
        for end in range(WINDOW - 1, len(clipdf)):
            t_end = clipdf["t"].iloc[end]
            if start is None:
                label = 0
            elif start <= t_end <= start + 2.0:
                label = 1
            elif t_end < start - 0.5 or t_end > start + 3.0:
                label = 0
            else:
                continue  # ambiguous moment around the fall: leave out of training and scoring
            rows.append({"subject": subject, "group": group, "clip": f"{subject}/{group}/{clip}", "t": t_end, "y": label,
                         **dict(zip(FEATURES, window_features(clipdf.iloc[end - WINDOW + 1 : end + 1])))})
    return pd.DataFrame(rows)


def fit(df: pd.DataFrame):
    scaler = StandardScaler().fit(df[FEATURES])
    model = LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000).fit(scaler.transform(df[FEATURES]), df["y"])
    return scaler, model


def clip_level(df: pd.DataFrame, prob: np.ndarray, threshold: float) -> tuple[float, float, int, int]:
    d = df.assign(p=prob)
    per_clip = d.groupby("clip").agg(group=("group", "first"), fired=("p", lambda s: bool((s >= threshold).any())))
    falls, adl = per_clip[per_clip["group"] == "Fall"], per_clip[per_clip["group"] == "ADL"]
    return (falls["fired"].mean() if len(falls) else float("nan"), adl["fired"].mean() if len(adl) else float("nan"), len(falls), len(adl))


def main() -> None:
    table = pd.read_csv(sys.argv[1])
    data = build(table)
    print(f"windows: {len(data)} | fall windows: {int(data['y'].sum())} | clips: {data['clip'].nunique()}")

    print("\nLeave-one-subject-out (always tested on a person it has never seen):")
    pooled_p, pooled_df = [], []
    for held_out in sorted(data["subject"].unique()):
        train, test = data[data["subject"] != held_out], data[data["subject"] == held_out]
        scaler, model = fit(train)
        prob = model.predict_proba(scaler.transform(test[FEATURES]))[:, 1]
        pooled_p.append(prob)
        pooled_df.append(test)
        auc = roc_auc_score(test["y"], prob) if test["y"].nunique() == 2 else float("nan")
        recall, false_alarm, nf, na = clip_level(test, prob, 0.5)
        print(f"  {held_out}: window AUC {auc:.3f} | falls caught {recall:.0%} of {nf} | normal clips with a false alarm {false_alarm:.0%} of {na}")

    prob, test = np.concatenate(pooled_p), pd.concat(pooled_df)
    print(f"\nAll held-out windows pooled: AUC {roc_auc_score(test['y'], prob):.3f}")
    print("Threshold trade-off (clip level, pooled over all four held-out subjects):")
    for thr in (0.5, 0.7, 0.8, 0.9, 0.95):
        recall, false_alarm, nf, na = clip_level(test, prob, thr)
        print(f"  threshold {thr:.2f}: falls caught {recall:.0%} of {nf} | false alarms on {false_alarm:.0%} of {na} normal clips")

    scaler, model = fit(data)
    out = {"window": WINDOW, "features": FEATURES, "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
           "coef": model.coef_[0].tolist(), "intercept": float(model.intercept_[0]),
           "source": "GMDCSA24 (Alam et al. 2024, MIT), acted indoor falls, 4 subjects"}
    json.dump(out, open(sys.argv[2], "w"), indent=2)
    print("\nsaved", sys.argv[2])


if __name__ == "__main__":
    main()

