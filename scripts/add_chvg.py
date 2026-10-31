"""Merge the CHVG dataset (CC BY 4.0, Ferdous & Ahsan 2022) into our 3-class training data.

CHVG annotations are Pascal VOC XML. Classes map by name:
    person -> 0 person;   white / yellow / blue / red (helmet colours) -> 1 helmet;   vest -> 2 vest
Everything else ("head" = bare head, "glass") is dropped: a missing helmet is inferred, not labelled.

Copies of one photo (same number before ".rf.") always land in the same split, so augmented
duplicates cannot leak from train into val/test.

Usage:  python scripts/add_chvg.py data/extra/chvg data/ppe3 data/ppe_merged
"""
from __future__ import annotations

import shutil
import sys
import xml.etree.ElementTree as ET
import zlib
from collections import Counter, defaultdict
from pathlib import Path

CLASS_OF = {"person": 0, "white": 1, "yellow": 1, "blue": 1, "red": 1, "vest": 2}
NAMES = ["person", "helmet", "vest"]


def split_of(group: str) -> str:
    bucket = zlib.crc32(group.encode()) % 10
    return "test" if bucket == 0 else "val" if bucket == 1 else "train"


def voc_to_yolo(xml_path: Path) -> list[str]:
    root = ET.parse(xml_path).getroot()
    size = root.find("size")
    width, height = float(size.findtext("width")), float(size.findtext("height"))
    lines = []
    for obj in root.findall("object"):
        cls = CLASS_OF.get(obj.findtext("name", "").strip().lower())
        if cls is None:
            continue
        box = obj.find("bndbox")
        x1, y1, x2, y2 = (float(box.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        x1, x2 = max(0.0, min(x1, width)), max(0.0, min(x2, width))
        y1, y2 = max(0.0, min(y1, height)), max(0.0, min(y2, height))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        lines.append(f"{cls} {(x1 + x2) / 2 / width:.6f} {(y1 + y2) / 2 / height:.6f} {(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}")
    return lines


def main(chvg: Path, base: Path, out: Path) -> None:
    for split in ("train", "val", "test"):
        for kind in ("images", "labels"):
            (out / kind / split).mkdir(parents=True, exist_ok=True)

    # 1. our existing data, unchanged (same test images as before, so old and new models can be compared)
    old_test = []
    for split in ("train", "val", "test"):
        for image in sorted((base / "images" / split).glob("*.*")):
            shutil.copy2(image, out / "images" / split / image.name)
            shutil.copy2(base / "labels" / split / f"{image.stem}.txt", out / "labels" / split / f"{image.stem}.txt")
            if split == "test":
                old_test.append(out / "images" / split / image.name)

    # 2. CHVG, grouped so augmented copies stay together
    groups = defaultdict(list)
    for xml in sorted(chvg.rglob("*.xml")):
        groups[xml.stem.split("_jpg")[0]].append(xml)
    print(f"CHVG: {sum(map(len, groups.values()))} files in {len(groups)} distinct source photos")

    counts, boxes, chvg_test = Counter(), Counter(), []
    for group, files in groups.items():
        split = split_of(group)
        for xml in files:
            image = xml.with_suffix(".jpg")
            if not image.exists():
                continue
            lines = voc_to_yolo(xml)
            name = f"chvg_{xml.stem.replace('.', '_')}"
            shutil.copy2(image, out / "images" / split / f"{name}.jpg")
            (out / "labels" / split / f"{name}.txt").write_text("\n".join(lines))
            counts[split] += 1
            boxes.update(NAMES[int(line.split()[0])] for line in lines)
            if split == "test":
                chvg_test.append(out / "images" / split / f"{name}.jpg")
    print("CHVG images per split:", dict(counts), "| boxes:", dict(boxes))

    # 3. yaml files: the merged set, plus the old and new test images scored separately
    base_yaml = f"path: {out.resolve().as_posix()}\nnames:\n" + "\n".join(f"  {i}: {n}" for i, n in enumerate(NAMES)) + "\n"
    (out / "data.yaml").write_text(base_yaml + "train: images/train\nval: images/val\ntest: images/test\n")
    for tag, files in (("old", old_test), ("chvg", chvg_test)):
        (out / f"test_{tag}.txt").write_text("\n".join(p.resolve().as_posix() for p in files))
        (out / f"eval_{tag}.yaml").write_text(base_yaml + f"train: test_{tag}.txt\nval: test_{tag}.txt\ntest: test_{tag}.txt\n")
    print(f"Wrote {out / 'data.yaml'}, eval_old.yaml ({len(old_test)} images), eval_chvg.yaml ({len(chvg_test)} images)")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
