"""Reduce the Ultralytics Construction-PPE dataset to the three classes we need.

Source classes kept:  Person(6) -> 0, helmet(0) -> 1, vest(2) -> 2
Everything else (gloves, boots, goggles, no_* ...) is dropped on purpose: a missing
helmet or vest is decided per worker by ppe.associate, not by a "missing" class.

Usage:  python scripts/prepare_dataset.py data/raw data/ppe3
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

KEEP = {6: 0, 0: 1, 2: 2}
NAMES = ["person", "helmet", "vest"]
SPLITS = ("train", "val", "test")


def find_root(raw: Path) -> Path:
    for path in [raw, *raw.rglob("*")]:
        if path.is_dir() and (path / "images").is_dir() and (path / "labels").is_dir():
            return path
    raise SystemExit(f"No images/ + labels/ folders found under {raw}")


def convert_label(src: Path) -> list[str]:
    lines = []
    for line in src.read_text().splitlines():
        parts = line.split()
        if parts and int(parts[0]) in KEEP:
            lines.append(" ".join([str(KEEP[int(parts[0])]), *parts[1:]]))
    return lines


def main(raw: Path, out: Path) -> None:
    root = find_root(raw)
    for split in SPLITS:
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        images = sorted((root / "images" / split).glob("*.*")) if (root / "images" / split).is_dir() else []
        counts = [0, 0, 0]
        for image in images:
            label = root / "labels" / split / f"{image.stem}.txt"
            lines = convert_label(label) if label.exists() else []
            shutil.copy2(image, out / "images" / split / image.name)
            (out / "labels" / split / f"{image.stem}.txt").write_text("\n".join(lines))
            for line in lines:
                counts[int(line.split()[0])] += 1
        print(f"{split}: {len(images)} images, boxes {dict(zip(NAMES, counts))}")

    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(NAMES))
    (out / "data.yaml").write_text(
        f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n"
    )
    print(f"Wrote {out / 'data.yaml'}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
