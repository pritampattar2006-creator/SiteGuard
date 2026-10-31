"""Turn the open "construction-safety" dataset (Roboflow 100 benchmark, via Hugging Face: Francesco/construction-safety-gsnvb) into our format.

Classes there: person, helmet, no-helmet, vest, no-vest. Ours: 0 person, 1 helmet, 2 vest, 3 head (no-helmet).
  - data/ppe6_rf/  : its train and valid photos, to add to training ("no-vest" boxes are left out, as a missing vest is inferred, not trained)
  - data/rf_test/  : its test photos, kept only to MEASURE (class 4 = no-vest, used for scoring the vest call; never trained on)
Near-duplicates of our own photos are dropped first, so the test is independent and training does not repeat photos we already have.
"""
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = next((ROOT / "data" / "extra" / "hf_safety" / "raw").rglob("construction-safety-gsnvb"))
OURS = ROOT / "data" / "ppe4"
MAP_TRAIN = {"person": 0, "helmet": 1, "vest": 2, "no-helmet": 3}
MAP_TEST = {**MAP_TRAIN, "no-vest": 4}


def dhash(image) -> np.ndarray:
    small = cv2.resize(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (9, 8), interpolation=cv2.INTER_AREA)
    return (small[:, 1:] > small[:, :-1]).flatten()


def hashes(folder: Path):
    out = []
    for p in sorted(folder.glob("*")):
        img = cv2.imread(str(p))
        if img is not None:
            out.append(dhash(img))
    return np.array(out)


def near_duplicate(h, pool, limit: int = 6) -> bool:
    return len(pool) > 0 and int((pool != h).sum(axis=1).min()) <= limit


def convert(split: str, mapping: dict, target: Path, target_split: str, avoid: np.ndarray) -> tuple[int, int]:
    data = json.loads((RAW / split / "_annotations.coco.json").read_text())
    names = {c["id"]: c["name"] for c in data["categories"]}
    boxes = {}
    for a in data["annotations"]:
        boxes.setdefault(a["image_id"], []).append(a)
    (target / "images" / target_split).mkdir(parents=True, exist_ok=True)
    (target / "labels" / target_split).mkdir(parents=True, exist_ok=True)
    kept = dropped = 0
    for im in data["images"]:
        path = RAW / split / im["file_name"]
        image = cv2.imread(str(path))
        if image is None:
            continue
        if near_duplicate(dhash(image), avoid):
            dropped += 1
            continue
        h, w = image.shape[:2]
        lines = []
        for a in boxes.get(im["id"], []):
            cls = mapping.get(names[a["category_id"]])
            if cls is None:
                continue
            x, y, bw, bh = a["bbox"]
            lines.append(f"{cls} {(x + bw / 2) / w:.6f} {(y + bh / 2) / h:.6f} {bw / w:.6f} {bh / h:.6f}")
        stem = f"rf_{split}_{Path(im['file_name']).stem[:60]}"
        shutil.copy(path, target / "images" / target_split / f"{stem}{path.suffix}")
        (target / "labels" / target_split / f"{stem}.txt").write_text("\n".join(lines))
        kept += 1
    return kept, dropped


if __name__ == "__main__":
    ours_eval = np.concatenate([hashes(OURS / "images" / "val"), hashes(OURS / "images" / "test")])
    ours_all = np.concatenate([ours_eval, hashes(OURS / "images" / "train")])
    for split in ("train", "valid"):
        print(split, "kept/dropped as near-duplicates of ANY of our photos:", convert(split, MAP_TRAIN, ROOT / "data" / "ppe6_rf", "train", ours_all))
    print("test kept/dropped as near-duplicates of ANY of our photos:", convert("test", MAP_TEST, ROOT / "data" / "rf_test", "test", ours_all))
