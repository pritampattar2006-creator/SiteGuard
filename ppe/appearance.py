"""Who is this, going by what they are wearing today? EXPERIMENTAL and strict: see the measurement below. Used when a person's face is not visible (back turned, helmet down, too far).

A "dress signature" is the colour make-up of the shirt/jacket and trousers (never the head, so taking a helmet off changes nothing).
Hi-vis yellow and orange are left out: nearly everybody on a site wears the same vest, so it says nothing about who is who.
Signatures are kept for one day only, because people change clothes. Matching is strict: if two people dress alike, nobody is named.

Measured on 160 clips of 4 people (one person per clip, so a rough guide only): colours alone separate people poorly across different
clips. At a similarity of 0.90, 4.8% of different-person pairs are wrongly accepted while only 20% of same-person pairs are; at 0.96
the wrong rate is 0.14% but only 4% of same-person pairs are accepted. So this is used only where it is reliable: the SAME footage seen
again (an identical upload, someone re-entering the same scene), with a very strict threshold. It is not a way to find a person across days.
"""
from __future__ import annotations

import json
import os

from .fileio import write_text_safely
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np

BANDS = ((0.28, 0.55), (0.58, 0.92))  # shirt / jacket, then trousers: as fractions of the person's height
HUE_BINS = 12


def signature(image, box, min_height: int = 100) -> np.ndarray | None:
    """The dress colours of one person, or None when the box is too small or cut off to read."""
    x1, y1, x2, y2 = [int(v) for v in box]
    h, w = y2 - y1, x2 - x1
    if h < min_height or w < 30 or x1 <= 1 or x2 >= image.shape[1] - 1 or y2 >= image.shape[0] - 1:
        return None  # a person at the edge of the picture is cut off, so the bands would be wrong
    parts = []
    for top, bottom in BANDS:
        crop = image[y1 + int(top * h): y1 + int(bottom * h), x1 + int(0.2 * w): x2 - int(0.2 * w)]
        if crop.size == 0:
            return None
        hue, sat, val = [c.astype(np.int32) for c in cv2.split(cv2.cvtColor(crop, cv2.COLOR_BGR2HSV))]
        hi_vis = (sat > 110) & (val > 140) & (hue >= 8) & (hue <= 45)
        keep = ~hi_vis
        if keep.sum() < 0.25 * keep.size:
            return None  # almost all vest: nothing about the person's own clothes can be read
        hue, sat, val = hue[keep], sat[keep], val[keep]
        black, white, grey = val < 60, (val >= 60) & (sat < 40) & (val > 180), (val >= 60) & (sat < 40) & (val <= 180)
        colour = ~(black | white | grey)
        hist = np.zeros(HUE_BINS + 3, dtype=np.float64)
        hist[:HUE_BINS] = np.bincount((hue[colour] * HUE_BINS // 180).clip(0, HUE_BINS - 1), minlength=HUE_BINS)
        hist[HUE_BINS:] = [black.sum(), white.sum(), grey.sum()]
        parts.append(hist / max(1.0, hist.sum()))
    return np.sqrt(np.concatenate(parts))  # square roots, so a plain dot product is the Hellinger similarity


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """1.0 for identical colour make-up, lower the more it differs (averaged over the two bands)."""
    return float(a @ b) / 2.0


class DressBook:
    """Today's dress signatures for each identity. Cleared when the day changes."""

    def __init__(self, path: Path, threshold: float = 0.97, margin: float = 0.02, offset_minutes: int = 330):
        self.path, self.threshold, self.margin, self.offset = Path(path), threshold, margin, offset_minutes
        self._lock = threading.Lock()
        self._people: dict[str, list[list[float]]] = {}
        self._day = self._today()
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("day") == self._day:
                self._people = data.get("people", {})

    def _today(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(minutes=self.offset)).strftime("%Y-%m-%d")

    def _roll(self) -> None:
        if self._today() != self._day:
            self._people, self._day = {}, self._today()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_text_safely(self.path, json.dumps({"day": self._day, "people": self._people}))

    def add(self, identity_id: str, sig: np.ndarray) -> None:
        with self._lock:
            self._roll()
            kept = self._people.setdefault(identity_id, [])
            if all(similarity(sig, np.asarray(s)) < 0.985 for s in kept):  # only keep genuinely different looks
                kept.append(sig.tolist())
                del kept[:-6]
                self._save()

    def match(self, sig: np.ndarray) -> tuple[str | None, str]:
        """(identity, state): state is 'match', 'unknown' (nobody dresses like this), or 'ambiguous' (several people do)."""
        with self._lock:
            self._roll()
            scored = sorted(((max(similarity(sig, np.asarray(s)) for s in sigs), k) for k, sigs in self._people.items() if sigs), reverse=True)
        if not scored or scored[0][0] < self.threshold - 0.1:
            return None, "unknown"
        if scored[0][0] >= self.threshold and (len(scored) < 2 or scored[0][0] - scored[1][0] >= self.margin):
            return scored[0][1], "match"
        return None, "ambiguous"

    def clear(self) -> None:
        with self._lock:
            self._people = {}
            self._save()
