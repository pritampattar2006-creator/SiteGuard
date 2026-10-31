"""Turn the GMDCSA24 fall videos into per-frame body-pose features.

For each video a pretrained pose model (YOLO11n-pose) finds the body joints of the most prominent person, and we keep a few
simple numbers per frame: how tilted the torso is, how wide the body is compared with its height, and where the head and hips are.
Labels come from the dataset's own timed annotations (e.g. "Falling (SW)[3.4 to 6]; Sitting[0 to 3.4]").

Dataset: GMDCSA24, Alam et al. 2024, MIT licence, https://doi.org/10.5281/zenodo.12921216

Usage:  python scripts/fall_features.py data/falls/gmdcsa24/<folder> data/falls/features.csv [--device 0|cpu] [--fps 10]
"""
from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

import cv2
import numpy as np

SEGMENT = re.compile(r"([A-Za-z][A-Za-z ()]*?)\s*\[\s*([0-9.]+)\s*to\s*([0-9.]+)\s*\]")
FIELDS = ["subject", "group", "clip", "t", "fall_start", "valid", "torso_angle", "aspect", "hip_y", "head_y", "head_hip", "height"]


def parse_classes(text: str) -> list[tuple[str, float, float]]:
    return [(name.strip(), float(a), float(b)) for name, a, b in SEGMENT.findall(text)]


def fall_start(segments) -> float | None:
    """When the fall begins in this clip, or None for a normal-activity clip."""
    starts = [a for name, a, _ in segments if name.lower().startswith("fall")]
    return min(starts) if starts else None


def frame_features(kps: np.ndarray, conf: np.ndarray, box: np.ndarray, frame_h: int):
    """kps: 17x2 pixel joints, conf: 17 scores, box: x1,y1,x2,y2. Returns None if the body is too hidden to measure."""
    def mid(i, j):
        pts = [kps[k] for k in (i, j) if conf[k] > 0.3]
        return np.mean(pts, axis=0) if pts else None

    shoulders, hips = mid(5, 6), mid(11, 12)
    x1, y1, x2, y2 = box
    w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
    if shoulders is None or hips is None:
        return None
    dx, dy = hips[0] - shoulders[0], hips[1] - shoulders[1]
    angle = math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))  # 0 = upright, 90 = horizontal
    head = kps[0] if conf[0] > 0.3 else shoulders
    return {
        "torso_angle": angle, "aspect": w / h, "hip_y": hips[1] / frame_h, "head_y": head[1] / frame_h,
        "head_hip": (hips[1] - head[1]) / h, "height": h / frame_h,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dataset")
    ap.add_argument("out")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--fps", type=float, default=10.0)
    ap.add_argument("--weights", default="yolo11n-pose.pt")
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.weights)
    root = Path(args.dataset)
    rows = 0
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for subject_dir in sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("Subject")):
            for group in ("ADL", "Fall"):
                table = subject_dir / f"{group}.csv"
                if not table.exists():
                    continue
                for line in csv.reader(open(table, encoding="utf-8-sig")):
                    if not line or not line[0].lower().endswith(".mp4"):
                        continue
                    clip = line[0].strip()
                    start = fall_start(parse_classes(" ".join(line[5:]))) if group == "Fall" else None
                    cap = cv2.VideoCapture(str(subject_dir / group / clip))
                    native = cap.get(cv2.CAP_PROP_FPS) or 30.0
                    stride = max(1, round(native / args.fps))
                    i = 0
                    while True:
                        ok, frame = cap.read()
                        if not ok:
                            break
                        if i % stride == 0:
                            res = model.predict(frame, imgsz=640, conf=0.3, device=args.device, verbose=False)[0]
                            if res.keypoints is not None and len(res.boxes):
                                big = int(np.argmax([(b[2] - b[0]) * (b[3] - b[1]) for b in res.boxes.xyxy.cpu().numpy()]))
                                feats = frame_features(res.keypoints.xy[big].cpu().numpy(), res.keypoints.conf[big].cpu().numpy(),
                                                       res.boxes.xyxy[big].cpu().numpy(), frame.shape[0])
                            else:
                                feats = None
                            writer.writerow({"subject": subject_dir.name, "group": group, "clip": clip, "t": round(i / native, 3),
                                             "fall_start": "" if start is None else start, "valid": int(feats is not None),
                                             **(feats or {k: "" for k in FIELDS[6:]})})
                            rows += 1
                        i += 1
                    cap.release()
            print(f"{subject_dir.name}: done ({rows} frames so far)", flush=True)
    print("wrote", args.out)


if __name__ == "__main__":
    main()
