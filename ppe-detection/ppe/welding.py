"""Welding watch: is someone welding in this video?

There is no trained welding model here (no open set of labelled welding photos was available), so this looks for what welding looks like on a fixed
camera: a very small, very bright, white-blue flash that flickers from frame to frame, with orange sparks around it, right next to a worker. A white
helmet, a lamp, the sky or a white wall do not flicker and are not that small, so they are ignored.

It only says "welding seen near a worker". It cannot see whether the welder wears a welding shield or gloves, so a welding event is a prompt for a
supervisor to check that, not a violation. Not measured on real welding footage: only on synthetic frames in the tests.
"""
from __future__ import annotations

from collections import deque

import cv2
import numpy as np

Box = tuple[float, float, float, float]


class WeldingMonitor:
    def __init__(self, window: int = 8, min_present: int = 4, min_change: float = 0.22, cooldown_s: float = 6.0, max_area_share: float = 0.004, camera_move_share: float = 0.12):
        self.camera_move_share = camera_move_share  # a moving camera makes lamps and glints flicker: nothing is judged while more than this share of the picture changes
        self._prev_gray = None
        self.window = window  # how many recent updates are considered
        self.min_present = min_present  # the flash must be there in at least this many of them
        self.min_change = min_change  # and its size must vary by this much (an arc flickers; a lamp or helmet does not)
        self.cooldown_s = cooldown_s
        self.max_area_share = max_area_share  # the flash covers at most this share of the picture
        self._seen: deque[tuple[float, float, float, float]] = deque(maxlen=window)  # (time, area, x, y); area 0 when nothing was seen
        self._last_alert = -1e9

    def _flash(self, frame: np.ndarray, people: list[Box]):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        core = ((hsv[..., 2] >= 245) & (hsv[..., 1] <= 70)).astype(np.uint8) * 255
        contours, _ = cv2.findContours(core, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        ceiling = self.max_area_share * frame.shape[0] * frame.shape[1]
        best = None
        for c in contours:
            area = cv2.contourArea(c)
            if not 3 <= area <= ceiling:
                continue
            x, y, w, h = cv2.boundingRect(c)
            cx, cy = x + w / 2, y + h / 2
            near = next((p for p in people if p[0] - 0.25 * (p[2] - p[0]) <= cx <= p[2] + 0.25 * (p[2] - p[0]) and p[1] <= cy <= p[3] + 0.1 * (p[3] - p[1])), None)
            if near is None:
                continue
            # sparks: orange, bright pixels in the area around the flash
            r = int(max(w, h) * 4 + 12)
            x0, y0, x1, y1 = max(0, x - r), max(0, y - r), min(frame.shape[1], x + w + r), min(frame.shape[0], y + h + r)
            patch = hsv[y0:y1, x0:x1]
            sparks = int((((patch[..., 0] >= 5) & (patch[..., 0] <= 28) & (patch[..., 1] >= 110) & (patch[..., 2] >= 190))).sum())
            if sparks < 4:
                continue
            if best is None or area > best[0]:
                best = (area, cx, cy, near)
        return best

    def update(self, t: float, frame: np.ndarray, people: list[Box]) -> list[dict]:
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        moving = self._prev_gray is not None and float((cv2.absdiff(gray, self._prev_gray) > 18).mean()) > self.camera_move_share
        self._prev_gray = gray
        if moving:
            self._seen.clear()
            return []
        found = self._flash(frame, people)
        self._seen.append((t, found[0] if found else 0.0, found[1] if found else 0.0, found[2] if found else 0.0))
        present = [s for s in self._seen if s[1] > 0]
        if found is None or len(present) < self.min_present or t - self._last_alert < self.cooldown_s:
            return []
        areas = np.array([s[1] for s in present])
        change = float(areas.std() / max(1.0, areas.mean()))
        jitter = float(np.hypot(np.std([s[2] for s in present]), np.std([s[3] for s in present])))
        if change < self.min_change and jitter < 2.0:
            return []  # steady, not flickering: a lamp or something white, not an arc
        self._last_alert = t
        x1, y1, x2, y2 = found[3]
        return [{"kind": "WELDING", "box": (x1, y1, x2, y2), "reason": "Flickering sparks, like a welding arc or a grinder, were seen next to a worker. Check the welding shield or face shield, gloves and fire safety.", "time_s": round(t, 2)}]
