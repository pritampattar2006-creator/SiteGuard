"""Backlit workers: a dark silhouette against a bright background (sunset, a bright window, sky) cannot have their gear judged.

Without this, a silhouette comes out as "no helmet, no vest" even though nothing can be seen either way. A violation for such a worker
is turned into "needs review" instead, and the video tracker ignores those frames, so no automatic case is sent for them.
"""
from __future__ import annotations

import cv2
import numpy as np

from .types import NEEDS_REVIEW, UNVERIFIABLE, VIOLATION

DARK_MEAN = 65  # the worker's own mean brightness (0-255) must be below this (measured: 90 flagged 8.5% of ordinary workers, 65 flags about 2%)
CONTRAST = 2.5  # and the surroundings at least this many times brighter
NOTE = "Backlit: this worker is a dark silhouette against a bright background, so their equipment cannot be judged. Please check the picture."


def is_backlit(image_bgr, box, margin: float = 0.5) -> bool:
    """True when the person's box is much darker than the ring of picture around it."""
    h, w = image_bgr.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    bw, bh = x2 - x1, y2 - y1
    if bw < 20 or bh < 40:
        return False
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    inner = gray[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    ox1, oy1, ox2, oy2 = max(0, int(x1 - margin * bw)), max(0, int(y1 - margin * bh)), min(w, int(x2 + margin * bw)), min(h, int(y2 + margin * bh))
    outer = gray[oy1:oy2, ox1:ox2].astype(np.float64)
    ring_sum = outer.sum() - float(inner.sum())
    ring_n = outer.size - inner.size
    if inner.size == 0 or ring_n < 0.3 * inner.size:
        return False  # almost no surroundings visible (the person fills the picture)
    inner_mean, ring_mean = float(inner.mean()), ring_sum / ring_n
    # A silhouette is clearest against the strip just above the head (sky, a bright window); the all-round ring can include dark ground and scaffolding.
    above = gray[max(0, y1 - int(0.4 * bh)):max(0, y1), max(0, x1):min(w, x2)]
    above_mean = float(above.mean()) if above.shape[0] >= 8 else 0.0
    return inner_mean < DARK_MEAN and max(ring_mean, above_mean) > CONTRAST * max(inner_mean, 1.0)


def apply_backlit(image_bgr, matches, verdicts) -> list[int]:
    """Turn violations for backlit workers into "needs review". Changes the verdicts in place; returns the worker ids affected."""
    held = []
    for match, verdict in zip(matches, verdicts):
        if verdict.status == VIOLATION and is_backlit(image_bgr, match.person.box):
            verdict.status = NEEDS_REVIEW
            verdict.helmet_state = verdict.vest_state = UNVERIFIABLE
            verdict.missing = []
            verdict.reason = NOTE
            held.append(verdict.worker_id)
    return held
