"""How good is the learned worker-down detector, clip by clip?

For each of the 79 fall clips and 81 normal-activity clips (GMDCSA24, 4 people) this records the highest fall score the detector reaches, then shows,
for several alert thresholds, how many fall clips would raise an alert and how many normal clips would raise a false one (split by day and low light).

Honest caveat: the classifier was trained on windows from these same clips, so these numbers are, if anything, optimistic.
  python scripts/eval_falls.py
"""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ppe.fall_model import FallClassifier, PoseFallMonitor  # noqa: E402

DATA = ROOT / "data" / "falls" / "gmdcsa24" / "GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos-master"
THRESHOLDS = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95)


def clips():
    for subject in range(1, 5):
        for kind in ("Fall", "ADL"):
            for row in csv.DictReader(open(DATA / f"Subject {subject}" / f"{kind}.csv", encoding="utf-8")):
                when = row.get("Time of Recording", "").lower()
                yield kind, subject, DATA / f"Subject {subject}" / kind / row["File Name"].strip(), ("night" in when or "off" in when)


def main() -> None:
    classifier = FallClassifier.load(ROOT / "weights" / "fall_model.json")
    seen: list[float] = []
    original = classifier.score
    classifier.score = lambda feats: (lambda s: (seen.append(s), s)[1])(original(feats))
    classifier.threshold = 9.0  # never alert: only the scores matter here
    monitor = PoseFallMonitor(str(ROOT / "weights" / "yolo11n-pose.pt"), classifier)
    rows = []
    for kind, subject, path, low in clips():
        if not path.exists():
            continue
        seen.clear()
        monitor._hist.clear(); monitor._last_t.clear(); monitor._alerted.clear(); monitor.model.predictor = None  # a fresh start for each clip
        cap = cv2.VideoCapture(str(path))
        fps, n = cap.get(cv2.CAP_PROP_FPS) or 30.0, 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if n % 2 == 0:
                monitor.update(n / fps, frame)
            n += 1
        rows.append((kind, subject, low, max(seen) if seen else 0.0))
        print(kind, subject, path.name, "low light" if low else "day", f"max score {rows[-1][3]:.2f}", flush=True)
    print("\nclips:", {k: sum(1 for r in rows if r[0] == k) for k in ("Fall", "ADL")})
    print(f"{'threshold':>9} | fall clips caught (all / day / low light) | normal clips falsely alerted (all / day / low light)")
    for t in THRESHOLDS:
        def share(kind, low=None):
            sel = [r for r in rows if r[0] == kind and (low is None or r[2] == low)]
            return f"{sum(1 for r in sel if r[3] >= t)}/{len(sel)}"
        print(f"{t:>9} | {share('Fall'):>8} / {share('Fall', False):>6} / {share('Fall', True):>6}      | {share('ADL'):>8} / {share('ADL', False):>6} / {share('ADL', True):>6}")


if __name__ == "__main__":
    main()
