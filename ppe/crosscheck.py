"""A second model looks again before a "no helmet" call is sent on automatically.

If the second model (weights/extras.pt) sees a helmet on the head of someone the main model says has none, the call is held back as
"needs review" instead of going to the supervisor as a violation. Measured on the held-out test photos (scripts/eval_crosscheck.py),
at a second-model confidence of 0.5 this held back none of the 88 real violations and caught 2 of the 6 false alarms: a small gain
that costs nothing, from a small sample.
"""
from __future__ import annotations

from .types import NEEDS_REVIEW, UNVERIFIABLE, VIOLATION

MIN_CONF = 0.5
NOTE = "A second model sees a helmet on this worker, so please check the picture."


def _on_head(box, point) -> bool:
    x1, y1, x2, y2 = box
    height = y2 - y1
    return x1 <= point[0] <= x2 and y1 - 0.15 * height <= point[1] <= y1 + 0.45 * height


def second_opinion(image, result, detector, cfg, min_conf: float = MIN_CONF) -> list[int]:
    """Hold back helmet violations the second model disagrees with. Changes the verdicts in `result`; returns the worker ids held back."""
    extra = getattr(detector, "extra_model", None)
    flagged = [(m, v) for m, v in zip(result.matches, result.verdicts) if v.status == VIOLATION and "NO HELMET" in v.missing]
    if extra is None or not flagged:
        return []  # nothing to double-check, so the second model is not even run
    helmets = [d for d in detector._detect_with(extra, detector.second_label_of, image, cfg) if d.label == "helmet" and d.conf >= min_conf]
    held = []
    for match, verdict in flagged:
        if any(_on_head(match.person.box, ((d.box[0] + d.box[2]) / 2, (d.box[1] + d.box[3]) / 2)) for d in helmets):
            verdict.missing = [item for item in verdict.missing if item != "NO HELMET"]
            verdict.helmet_state = UNVERIFIABLE  # the video tracker ignores frames like this, so no incident is raised from them
            if not verdict.missing:
                verdict.status = NEEDS_REVIEW
            verdict.reason = f"{verdict.reason} {NOTE}".strip()
            held.append(verdict.worker_id)
    return held
