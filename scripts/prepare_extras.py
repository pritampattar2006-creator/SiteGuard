"""Build a 6-class dataset (person, helmet, vest, gloves, boots, goggles) from Construction-PPE.

Source ids: helmet 0, gloves 1, vest 2, boots 3, goggles 4, none 5, Person 6, no_helmet 7, no_goggle 8, no_gloves 9, no_boots 10.
The "no_*" and "none" classes are dropped: missing equipment is inferred per worker, not detected.

Usage:  python scripts/prepare_extras.py data/raw data/ppe6
"""
from __future__ import annotations

import shutil
import sys
from collections import Counter
from pathlib import Path

KEEP = {6: 0, 0: 1, 2: 2, 1: 3, 3: 4, 4: 5}
NAMES = ["person", "helmet", "vest", "gloves", "boots", "goggles"]
SPLITS = ("train", "val", "test")


def find_root(raw: Path) -> Path:
    for path in [raw, *raw.rglob("*")]:
        if path.is_dir() and (path / "images").is_dir() and (path / "labels").is_dir():
            return path
    raise SystemExit(f"No images/ + labels/ folders found under {raw}")


def main(raw: Path, out: Path) -> None:
    root = find_root(raw)
    for split in SPLITS:
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        counts, images = Counter(), sorted((root / "images" / split).glob("*.*"))
        for image in images:
            label = root / "labels" / split / f"{image.stem}.txt"
            lines = []
            for line in (label.read_text().splitlines() if label.exists() else []):
                parts = line.split()
                if parts and int(parts[0]) in KEEP:
                    lines.append(" ".join([str(KEEP[int(parts[0])]), *parts[1:]]))
                    counts[NAMES[KEEP[int(parts[0])]]] += 1
            shutil.copy2(image, out / "images" / split / image.name)
            (out / "labels" / split / f"{image.stem}.txt").write_text("\n".join(lines))
        print(f"{split}: {len(images)} images | boxes {dict(counts)}")
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(NAMES))
    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n"
    )
    print(f"Wrote {out / 'data.yaml'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
