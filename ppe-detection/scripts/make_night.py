"""Make night-style data from daytime photos (brightness, gamma and noise), as the dataset notes recommend when real night data is not available.

  - data/ppe5_night : darkened copies of a share of the TRAINING photos (same labels), added to training
  - data/ppe4_night : a darkened copy of the held-out TEST photos, used only to measure day versus night

The validation and test photos used for the normal scores are never changed, so numbers stay comparable.
"""
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "ppe4"


def darken(image, rng):
    gamma, scale = rng.uniform(1.8, 2.8), rng.uniform(0.35, 0.65)
    x = (image.astype(np.float32) / 255.0) ** gamma * scale
    x = np.clip(x + rng.normal(0, rng.uniform(0.01, 0.04), x.shape), 0, 1)
    out = (x * 255).astype(np.uint8)
    return cv2.GaussianBlur(out, (3, 3), 0) if rng.random() < 0.5 else out


def build(split: str, target: Path, share: float, seed: int) -> int:
    rng = np.random.default_rng(seed)
    images = sorted((SRC / "images" / split).glob("*"))
    (target / "images" / split).mkdir(parents=True, exist_ok=True)
    (target / "labels" / split).mkdir(parents=True, exist_ok=True)
    made = 0
    for path in images:
        if rng.random() > share:
            continue
        image = cv2.imread(str(path))
        label = SRC / "labels" / split / f"{path.stem}.txt"
        if image is None or not label.exists():
            continue
        cv2.imwrite(str(target / "images" / split / f"{path.stem}_night.jpg"), darken(image, rng), [cv2.IMWRITE_JPEG_QUALITY, 92])
        shutil.copy(label, target / "labels" / split / f"{path.stem}_night.txt")
        made += 1
    return made


if __name__ == "__main__":
    print("training copies:", build("train", ROOT / "data" / "ppe5_night", share=0.45, seed=7))
    print("night test photos:", build("test", ROOT / "data" / "ppe4_night", share=1.0, seed=11))
    (ROOT / "data" / "ppe5.yaml").write_text(
        f"path: {ROOT.as_posix()}/data\n"
        "train:\n  - ppe4/images/train\n  - ppe5_night/images/train\n"
        "val: ppe4/images/val\ntest: ppe4/images/test\n"
        "names:\n  0: person\n  1: helmet\n  2: vest\n  3: head\n", encoding="utf-8")
    print("wrote data/ppe5.yaml")
