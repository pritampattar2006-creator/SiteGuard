"""How right are the per-worker verdicts? Scored on labelled photos the model was not trained on.

For every labelled person, the ground truth comes from the dataset's own boxes:
  - helmet worn      : a labelled helmet sits on the person's head
  - helmet missing   : a labelled bare head ("head" class) sits on the person's head
  - vest worn        : a labelled vest sits on the person's torso
(a missing vest is not labelled in this data, so the vest is scored only for false alarms on people who do wear one)

  python scripts/eval_workers.py                          # test split with the current settings
  python scripts/eval_workers.py --sweep                  # try thresholds on the validation split, then score the test split with the best
"""
import argparse
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from ppe.config import Config  # noqa: E402
from ppe.detector import Detector  # noqa: E402
from ppe.enhance import maybe_enhance  # noqa: E402
from ppe.pipeline import analyze  # noqa: E402
from ppe.types import NEEDS_REVIEW, VIOLATION  # noqa: E402

DATA = ROOT / "data" / "ppe4"
ENHANCE = "auto"


def read_labels(path: Path, width: int, height: int):
    boxes = {0: [], 1: [], 2: [], 3: [], 4: []}  # 4 = no vest, only in datasets that have it (ppe4_vest)
    if path.exists():
        for line in path.read_text().splitlines():
            c, cx, cy, w, h = line.split()[:5]
            cx, cy, w, h = float(cx) * width, float(cy) * height, float(w) * width, float(h) * height
            boxes[int(c)].append((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return boxes


def centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def inside(point, box, top=0.0, bottom=1.0):
    x, y = point
    return box[0] <= x <= box[2] and box[1] + top * (box[3] - box[1]) <= y <= box[1] + bottom * (box[3] - box[1])


def iou(a, b):
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


class Cached:
    """Pretends to be a detector but returns detections that were already computed, so thresholds can be swept quickly."""

    def __init__(self, detections):
        self.detections, self.last_objects = detections, []

    def detect(self, image, cfg):
        return self.detections


def collect(split: str, detector, config: Config):
    """Run the detector once per photo and keep its raw detections with the ground truth."""
    items = []
    for path in sorted((DATA / "images" / split).glob("*")):
        image = cv2.imread(str(path))
        if image is None:
            continue
        height, width = image.shape[:2]
        gt = read_labels(DATA / "labels" / split / f"{path.stem}.txt", width, height)
        image, brightened = maybe_enhance(image, config, ENHANCE)
        detector.dark = brightened  # dark photos are brightened first, exactly as the real pipeline does
        detections = detector.detect(image, config)
        items.append((image, gt, detections, list(detector.last_objects)))
    return items


def score(items, config: Config, min_person_px: int = 60) -> dict:
    m = dict(people=0, missed=0, tp=0, fp=0, fn=0, tn=0, review_bare=0, review_helmeted=0, vest_worn=0, vest_false=0, vest_review=0, vm_total=0, vm_tp=0, vm_review=0)
    for image, gt, detections, objects in items:
        fake = Cached(detections)
        fake.last_objects = objects
        result = analyze(image, config, fake)
        found = [(mt.person.box, v) for mt, v in zip(result.matches, result.verdicts)]
        for person in gt[0]:
            if person[3] - person[1] < min_person_px:
                continue
            helmet_on = any(inside(centre(h), person, -0.15, 0.45) for h in gt[1])
            bare = any(inside(centre(h), person, -0.15, 0.45) for h in gt[3])
            vest_on = any(inside(centre(v), person, 0.15, 0.85) for v in gt[2])
            vest_off = any(inside(centre(v), person, 0.15, 0.85) for v in gt[4]) and not vest_on
            best = max(found, key=lambda f: iou(f[0], person), default=None)
            m["people"] += 1
            if best is None or iou(best[0], person) < 0.5:
                m["missed"] += 1
                continue
            verdict = best[1]
            says_missing = "NO HELMET" in verdict.missing and verdict.status == VIOLATION
            says_review = verdict.status == NEEDS_REVIEW
            if bare and not helmet_on:
                m["tp" if says_missing else "review_bare" if says_review else "fn"] += 1
            elif helmet_on and not bare:
                m["fp" if says_missing else "review_helmeted" if says_review else "tn"] += 1
            if vest_off:
                m["vm_total"] += 1
                if "NO VEST" in verdict.missing and verdict.status == VIOLATION:
                    m["vm_tp"] += 1
                elif says_review:
                    m["vm_review"] += 1
            if vest_on:
                m["vest_worn"] += 1
                if "NO VEST" in verdict.missing and verdict.status == VIOLATION:
                    m["vest_false"] += 1
                elif says_review:
                    m["vest_review"] += 1
    tp, fp, fn, rb = m["tp"], m["fp"], m["fn"], m["review_bare"]
    m["precision"] = tp / (tp + fp) if tp + fp else 0.0
    m["recall"] = tp / (tp + fn + rb) if tp + fn + rb else 0.0
    m["recall_incl_review"] = (tp + rb) / (tp + fn + rb) if tp + fn + rb else 0.0
    m["f1"] = 2 * m["precision"] * m["recall"] / (m["precision"] + m["recall"]) if m["precision"] + m["recall"] else 0.0
    m["vest_false_rate"] = m["vest_false"] / m["vest_worn"] if m["vest_worn"] else 0.0
    return m


def show(title: str, m: dict) -> None:
    print(f"\n{title}")
    print(f"  labelled people judged {m['people']}   not found by the detector {m['missed']} ({m['missed'] / max(1, m['people']):.1%})")
    print(f"  HELMET MISSING   caught {m['tp']}   false alarms {m['fp']}   missed {m['fn']}   to review {m['review_bare']} bare / {m['review_helmeted']} helmeted   correctly passed {m['tn']}")
    print(f"                   precision {m['precision']:.3f}   recall {m['recall']:.3f}   recall incl. review {m['recall_incl_review']:.3f}   F1 {m['f1']:.3f}")
    if m["vm_total"]:
        print(f"  VEST MISSING     caught {m['vm_tp']} of {m['vm_total']} workers truly without a vest ({m['vm_tp'] / m['vm_total']:.1%}); a further {m['vm_review']} sent to review")
    print(f"  VEST             false alarms {m['vest_false']} of {m['vest_worn']} people wearing one ({m['vest_false_rate']:.1%}); sent to review {m['vest_review']}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--weights", default=str(ROOT / "weights" / "best.pt"))
    p.add_argument("--dataset", default="ppe4", help="folder under data/ with images/ and labels/ (ppe4_night is the darkened test set)")
    p.add_argument("--sweep", action="store_true", help="tune helmet and vest thresholds on the validation split, then score the test split")
    p.add_argument("--tile-grid", type=int, default=None, help="look at zoomed tiles too (2 = 2x2) to find small or distant workers")
    p.add_argument("--imgsz", type=int, default=None, help="inference size in pixels (default: the Config value)")
    p.add_argument("--augment", action="store_true", help="test-time augmentation: also look at the photo flipped and rescaled")
    p.add_argument("--night-weights", default=None, help="a night-trained model, used only for dark photos")
    p.add_argument("--enhance", default="auto", choices=["auto", "off"], help="brighten dark photos first (auto), or not (off)")
    p.add_argument("--helmet-conf", type=float)
    p.add_argument("--vest-conf", type=float)
    args = p.parse_args()

    global DATA, ENHANCE
    ENHANCE = args.enhance
    DATA = ROOT / "data" / args.dataset
    base = Config()
    if args.tile_grid is not None:
        base = replace(base, tile_grid=args.tile_grid)
    if args.imgsz is not None:
        base = replace(base, imgsz=args.imgsz)
    detector = Detector(args.weights, augment=args.augment, night_weights=args.night_weights)
    if args.sweep:
        val = collect("val", detector, base)
        best, best_cfg = None, base
        print(f"{'helmet_conf':>11} {'vest_conf':>9} | helmet precision recall F1 missed | vest false-alarm | sent to review (helmet+vest)")
        for hc in (0.20, 0.25, 0.30, 0.35):
            for vc in (0.15, 0.20, 0.25, 0.30):
                cfg = replace(base, helmet_conf=hc, vest_conf=vc)
                m = score(val, cfg)
                burden = m["review_helmeted"] + m["vest_review"]
                print(f"{hc:>11} {vc:>9} | {m['precision']:>16.3f} {m['recall']:>6.3f} {m['f1']:.3f} {m['fn']:>6} | {m['vest_false_rate']:>14.1%} | {burden}")
                # best helmet F1, and among near-ties the lowest vest false-alarm rate
                key = (round(m["f1"], 3), -round(m["vest_false_rate"], 3), -burden)
                if best is None or key > best:
                    best, best_cfg = key, cfg
        print(f"\nbest on validation: helmet_conf {best_cfg.helmet_conf}, vest_conf {best_cfg.vest_conf}")
        test = collect("test", detector, base)
        show("TEST split, current default settings", score(test, base))
        show(f"TEST split, tuned settings (helmet {best_cfg.helmet_conf}, vest {best_cfg.vest_conf})", score(test, best_cfg))
        return
    cfg = base
    if args.helmet_conf is not None:
        cfg = replace(cfg, helmet_conf=args.helmet_conf)
    if args.vest_conf is not None:
        cfg = replace(cfg, vest_conf=args.vest_conf)
    show("TEST split", score(collect("test", detector, base), cfg))


if __name__ == "__main__":
    main()
