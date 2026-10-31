"""Falling-object watch: a large object moving downward near a worker, or hitting one.

There is no trained model for falling objects (steel beams, bricks, planks, buckets all look different), so this works from motion alone, on a
fixed camera: it looks for big areas that change between frames, ignores the people, follows each one, and calls it "falling" when it keeps
dropping. It then compares it with the people:

  FALLING OBJECT      something big is dropping in view, nobody close to it (logged, no alarm)
  OBJECT NEAR WORKER  it is dropping close to a worker: a near miss or about to hit (alarm)
  OBJECT HIT WORKER   it overlaps a worker's body while dropping (alarm)

A hit is only "hit" when the falling shape overlaps a person; whether the person is hurt is not known, so it is always an alert for a person to go
and check. Accuracy has only been checked on the clips in the test cases; a handheld or moving camera breaks the method.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

Box = tuple[float, float, float, float]


@dataclass
class _Track:
    ident: int
    box: Box
    history: list[tuple[float, float, float]] = field(default_factory=list)  # (time, centre x, centre y)
    missed: int = 0
    last_alert: float = -1e9


def _overlap(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


class HazardMonitor:
    def __init__(self, min_area_share: float = 0.004, min_drop_share: float = 0.05, near_margin: float = 0.6, steps: int = 3, cooldown_s: float = 2.0,
                 camera_move_share: float = 0.12):
        self.camera_move_share = camera_move_share  # if more than this share of the picture changes between two frames, the camera is moving: nothing is judged
        self.min_area_share = min_area_share  # a falling thing must cover at least this share of the picture
        self.min_drop_share = min_drop_share  # and must have dropped by at least this share of the picture height
        self.near_margin = near_margin  # how far from a person still counts as "near", as a share of the person's height
        self.steps = steps  # how many consecutive updates it must keep dropping
        self.cooldown_s = cooldown_s
        self._prev: np.ndarray | None = None
        self.camera_moving = False
        self._tracks: list[_Track] = []
        self._next = 1

    def _blobs(self, gray: np.ndarray, people: list[Box]) -> list[Box]:
        if self._prev is None:
            return []
        diff = cv2.absdiff(gray, self._prev)
        mask = (diff > 18).astype(np.uint8) * 255
        self.camera_moving = float((mask > 0).mean()) > self.camera_move_share
        if self.camera_moving:
            return []
        for x1, y1, x2, y2 in people:  # people moving is not an object falling
            px, py = 0.12 * (x2 - x1), 0.08 * (y2 - y1)
            mask[max(0, int(y1 - py)):int(y2 + py), max(0, int(x1 - px)):int(x2 + px)] = 0
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        floor = self.min_area_share * gray.shape[0] * gray.shape[1]
        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if w * h >= floor and cv2.contourArea(c) >= 0.35 * w * h * 0.5:
                boxes.append((float(x), float(y), float(x + w), float(y + h)))
        return boxes

    def update(self, t: float, frame: np.ndarray, people: list[Box]) -> list[dict]:
        """Feed one frame (and the people found in it). Returns new alerts: dicts with kind, box, reason, alarm."""
        scale = 1.0
        if frame.shape[1] > 640:  # look at a small copy: quicker, and the same thresholds work for a phone or a 4K camera
            scale = 640 / frame.shape[1]
            frame = cv2.resize(frame, (640, max(1, int(frame.shape[0] * scale))))
            people = [tuple(v * scale for v in p) for p in people]
        gray = cv2.GaussianBlur(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (5, 5), 0)
        blobs = self._blobs(gray, people)
        self._prev = gray
        if self.camera_moving:  # a moving camera makes everything look as if it moves: forget what was being followed and judge nothing
            self._tracks = []
            return []
        height = frame.shape[0]
        # follow each blob from the previous update (nearest centre)
        for tr in self._tracks:
            tr.missed += 1
        for box in blobs:
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            best = min(self._tracks, key=lambda tr: np.hypot(tr.history[-1][1] - cx, tr.history[-1][2] - cy), default=None)
            reach = 0.25 * max(box[2] - box[0], box[3] - box[1]) + 0.12 * height
            if best is not None and np.hypot(best.history[-1][1] - cx, best.history[-1][2] - cy) <= reach and best.missed >= 1:
                best.box, best.missed = box, 0
                best.history.append((t, cx, cy))
            else:
                self._tracks.append(_Track(self._next, box, [(t, cx, cy)]))
                self._next += 1
        self._tracks = [tr for tr in self._tracks if tr.missed <= 2]
        alerts = []
        for tr in self._tracks:
            if tr.missed or len(tr.history) < self.steps + 1:
                continue
            recent = tr.history[-(self.steps + 1):]
            drops = [b[2] - a[2] for a, b in zip(recent, recent[1:])]
            total = recent[-1][2] - recent[0][2]
            if not (all(d > 0 for d in drops) and total >= self.min_drop_share * height):
                continue  # not clearly dropping
            if t - tr.last_alert < self.cooldown_s:
                continue
            kind, reason, alarm = "FALLING OBJECT", "A large object is dropping.", False
            box = tr.box
            for person in people:
                height_p = person[3] - person[1]
                zone = (person[0] - self.near_margin * height_p, person[1] - self.near_margin * height_p, person[2] + self.near_margin * height_p, person[3] + 0.1 * height_p)
                # the part of the object that overlaps the person is masked out as "person movement", so contact means the visible part reaches
                # the person's box (allowing for that masked margin) with real horizontal overlap
                reach = (box[0], box[1], box[2], box[3] + 0.1 * height_p)
                across = min(box[2], person[2]) - max(box[0], person[0])
                if _overlap(reach, person) > 0 and across >= 0.3 * min(box[2] - box[0], person[2] - person[0]):
                    kind, reason, alarm = "OBJECT HIT WORKER", "A dropping object overlaps a worker.", True
                    break
                if _overlap(box, zone) > 0:
                    kind, reason, alarm = "OBJECT NEAR WORKER", "An object is dropping close to a worker.", True
            tr.last_alert = t
            alerts.append({"kind": kind, "box": tuple(v / scale for v in box), "reason": reason, "alarm": alarm, "time_s": round(t, 2), "track": tr.ident})
        return alerts
