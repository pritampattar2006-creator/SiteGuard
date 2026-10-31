"""Score models on the held-out test photos (never used for training) so a new model is only adopted if it is really better.

  python scripts/compare_models.py weights/best_v3.pt runs/train/ppe_v4/weights/best.pt
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    from ultralytics import YOLO

    models = sys.argv[1:]
    if not models:
        sys.exit("Give at least one weights file.")
    table = []
    for path in models:
        result = YOLO(path).val(data=str(ROOT / "data" / "ppe4" / "data.yaml"), split="test", imgsz=960, conf=0.001, plots=False, verbose=False)
        names = result.names
        per_class = {names[int(c)]: round(float(ap), 3) for c, ap in zip(result.box.ap_class_index, result.box.ap50)}
        table.append((path, per_class, round(float(result.box.map50), 3), round(float(result.box.map), 3)))
    for path, per_class, m50, m5095 in table:
        print(f"\n{path}\n  mAP50 {m50}   mAP50-95 {m5095}\n  AP50 per class: {per_class}")


if __name__ == "__main__":
    main()
