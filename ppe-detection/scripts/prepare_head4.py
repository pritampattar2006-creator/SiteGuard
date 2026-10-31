"""Build a 4-class dataset: person, helmet, vest, head.

`head` is a bare or covered head with no helmet (Construction-PPE `no_helmet`, CHVG `head`). Teaching the model what a
head without a helmet looks like gives caps, beanies and head cloths somewhere to go other than "helmet".

Splits match data/ppe_merged: Construction-PPE keeps its own train/val/test; CHVG is split by source photo.

Usage:  python scripts/prepare_head4.py data/raw data/extra/chvg data/ppe4
"""
from __future__ import annotations

import shutil
import sys
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from pathlib import Path

NAMES = ["person", "helmet", "vest", "head"]
CPPE = {6: 0, 0: 1, 2: 2, 7: 3}  # Construction-PPE: Person, helmet, vest, no_helmet
CHVG = {"person": 0, "white": 1, "yellow": 1, "blue": 1, "red": 1, "vest": 2, "head": 3}


def chvg_split(group: str) -> str:
    bucket = zlib.crc32(group.encode()) % 10
    return "test" if bucket == 0 else "val" if bucket == 1 else "train"


def voc_lines(xml_path: Path) -> list[str]:
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    w, h = float(size.findtext("width")), float(size.findtext("height"))
    lines = []
    for obj in root.findall("object"):
        cls = CHVG.get(obj.findtext("name", "").strip().lower())
        if cls is None:
            continue
        b = obj.find("bndbox")
        x1, y1, x2, y2 = (float(b.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        x1, x2, y1, y2 = max(0.0, min(x1, w)), max(0.0, min(x2, w)), max(0.0, min(y1, h)), max(0.0, min(y2, h))
        if x2 - x1 >= 2 and y2 - y1 >= 2:
            lines.append(f"{cls} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return lines


def main(cppe_raw: Path, chvg: Path, out: Path) -> None:
    for kind in ("images", "labels"):
        for split in ("train", "val", "test"):
            (out / kind / split).mkdir(parents=True, exist_ok=True)
    counts: dict[str, Counter] = {s: Counter() for s in ("train", "val", "test")}

    for split in counts:
        for image in sorted((cppe_raw / "images" / split).glob("*.*")):
            label = cppe_raw / "labels" / split / f"{image.stem}.txt"
            lines = []
            for line in (label.read_text().splitlines() if label.exists() else []):
                parts = line.split()
                if parts and int(parts[0]) in CPPE:
                    lines.append(" ".join([str(CPPE[int(parts[0])]), *parts[1:]]))
            shutil.copy2(image, out / "images" / split / image.name)
            (out / "labels" / split / f"{image.stem}.txt").write_text("\n".join(lines))
            counts[split].update(NAMES[int(l.split()[0])] for l in lines)

    for xml in sorted(chvg.rglob("*.xml")):
        image = xml.with_suffix(".jpg")
        if not image.exists():
            continue
        split = chvg_split(xml.stem.split("_jpg")[0])
        name = f"chvg_{xml.stem.replace('.', '_')}"
        lines = voc_lines(xml)
        shutil.copy2(image, out / "images" / split / f"{name}.jpg")
        (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
        counts[split].update(NAMES[int(l.split()[0])] for l in lines)

    for split, c in counts.items():
        print(f"{split}: {len(list((out / 'images' / split).glob('*')))} images | {dict(c)}")
    names = "\n".join(f"  {i}: {n}" for i, n in enumerate(NAMES))
    (out / "data.yaml").write_text(f"path: {out.resolve().as_posix()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n{names}\n")
    print("wrote", out / "data.yaml")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
