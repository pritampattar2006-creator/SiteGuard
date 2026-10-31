"""Give our held-out test photos a ground truth for "no vest", using the open construction-safety dataset's own "no-vest" boxes.

Our labels never said where a vest was missing, so the vest call could only be scored for false alarms. That dataset covers the same photos
and does label them. Each of our test photos is matched to its twin by a picture fingerprint; the boxes are carried over only when the twin's
person boxes line up with ours (so a crop or a different size never gives a wrong truth).

Writes data/ppe4_vest/{images,labels}/test: our labels (classes 0 to 3) plus class 4 = "no vest".
"""
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = next((ROOT / "data" / "extra" / "hf_safety" / "raw").rglob("construction-safety-gsnvb"))
OURS = ROOT / "data" / "ppe4"
OUT = ROOT / "data" / "ppe4_vest"
CLASSES = {"person": 0, "helmet": 1, "vest": 2, "no-helmet": 3, "no-vest": 4}


def dhash(image) -> np.ndarray:
    small = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
    return (small[:, 1:] > small[:, :-1]).flatten()


def iou(a, b) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def twins():
    """Every photo of the open dataset: (fingerprint, {class: [normalised x1,y1,x2,y2]})."""
    out = []
    for split in ("train", "valid", "test"):
        data = json.loads((RAW / split / "_annotations.coco.json").read_text())
        names = {c["id"]: c["name"] for c in data["categories"]}
        boxes = {}
        for a in data["annotations"]:
            if names[a["category_id"]] in CLASSES:
                boxes.setdefault(a["image_id"], []).append(a)
        for im in data["images"]:
            image = cv2.imread(str(RAW / split / im["file_name"]))
            if image is None:
                continue
            w, h = im["width"], im["height"]
            grouped = {}
            for a in boxes.get(im["id"], []):
                x, y, bw, bh = a["bbox"]
                grouped.setdefault(CLASSES[names[a["category_id"]]], []).append((x / w, y / h, (x + bw) / w, (y + bh) / h))
            out.append((dhash(image), grouped))
    return out


if __name__ == "__main__":
    pool = twins()
    hashes = np.array([p[0] for p in pool])
    shutil.rmtree(OUT, ignore_errors=True)
    (OUT / "images" / "test").mkdir(parents=True)
    (OUT / "labels" / "test").mkdir(parents=True)
    matched = aligned = with_no_vest = 0
    for path in sorted((OURS / "images" / "test").glob("*")):
        image = cv2.imread(str(path))
        label_path = OURS / "labels" / "test" / f"{path.stem}.txt"
        if image is None or not label_path.exists():
            continue
        distance = (hashes != dhash(image)).sum(axis=1)
        best = int(distance.argmin())
        if distance[best] > 6:
            continue
        matched += 1
        h, w = image.shape[:2]
        ours = [l.split() for l in label_path.read_text().splitlines() if l.strip()]
        our_persons = [(float(x) - float(bw) / 2, float(y) - float(bh) / 2, float(x) + float(bw) / 2, float(y) + float(bh) / 2) for c, x, y, bw, bh in (o[:5] for o in ours) if c == "0"]
        their_persons = pool[best][1].get(0, [])
        if not our_persons or not their_persons:
            continue
        overlaps = [max(iou(p, q) for q in their_persons) for p in our_persons]
        if min(overlaps) < 0.6:  # their boxes do not line up with ours (a crop, or a different set of people): no truth from this twin
            continue
        aligned += 1
        extra = [f"4 {(a + c) / 2:.6f} {(b + d) / 2:.6f} {c - a:.6f} {d - b:.6f}" for a, b, c, d in pool[best][1].get(4, [])]
        with_no_vest += bool(extra)
        shutil.copy(path, OUT / "images" / "test" / path.name)
        (OUT / "labels" / "test" / f"{path.stem}.txt").write_text("\n".join([" ".join(o) for o in ours] + extra))
    print(f"test photos with a twin: {matched}; boxes line up: {aligned}; of those with a labelled missing vest: {with_no_vest}")
