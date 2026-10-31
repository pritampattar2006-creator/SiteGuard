"""Would a second model's opinion make the automatic "no helmet" calls more trustworthy?

For every worker the main model flags as having no helmet, a second model (weights/extras.pt) looks at the same photo. If it sees a
helmet on that worker's head, the call would be held back for a person to review. This reports, on the held-out test photos,
how many real violations that would wrongly hold back and how many false alarms it would catch.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2  # noqa: E402

from ppe.config import Config  # noqa: E402
from ppe.detector import Detector  # noqa: E402
from ppe.pipeline import analyze  # noqa: E402
from ppe.types import VIOLATION  # noqa: E402
from scripts.eval_workers import DATA, centre, inside, iou, read_labels  # noqa: E402

cfg = Config()
detector = Detector(str(ROOT / "weights" / "best.pt"), extra_weights=str(ROOT / "weights" / "extras.pt"))
assert detector.extra_model is not None and "helmet" in detector.second_label_of.values()

THRESHOLDS = (0.25, 0.35, 0.5, 0.6)
tally = {t: dict(kept_true=0, held_true=0, kept_false=0, held_false=0) for t in THRESHOLDS}
for path in sorted((DATA / "images" / "test").glob("*")):
    image = cv2.imread(str(path))
    if image is None:
        continue
    h, w = image.shape[:2]
    gt = read_labels(DATA / "labels" / "test" / f"{path.stem}.txt", w, h)
    result = analyze(image, cfg, detector)
    second = [d for d in detector._detect_with(detector.extra_model, detector.second_label_of, image, cfg) if d.label == "helmet"]
    flagged = [(m.person.box, v) for m, v in zip(result.matches, result.verdicts) if v.status == VIOLATION and "NO HELMET" in v.missing]
    for box, _ in flagged:
        match = max(gt[0], key=lambda g: iou(g, box), default=None)
        if match is None or iou(match, box) < 0.5:
            continue
        helmet_on = any(inside(centre(x), match, -0.15, 0.45) for x in gt[1])
        bare = any(inside(centre(x), match, -0.15, 0.45) for x in gt[3])
        if helmet_on == bare:
            continue  # unlabelled either way: cannot score
        for t in THRESHOLDS:
            sees = any(d.conf >= t and inside(centre(d.box), box, -0.15, 0.45) for d in second)
            key = ("held_" if sees else "kept_") + ("false" if helmet_on else "true")
            tally[t][key] += 1

print("second model's helmet confidence | real violations kept / wrongly held back | false alarms caught / still sent")
for t, c in tally.items():
    real = c["kept_true"] + c["held_true"]
    false = c["kept_false"] + c["held_false"]
    print(f"{t:>32} | {c['kept_true']:>3} / {c['held_true']:<3}  of {real:<3}               | {c['held_false']:>3} / {c['kept_false']:<3} of {false}")
