"""A second opinion on every "person" box, so an object is not treated as a worker.

The main model can mistake a large object for a person, for example an orange concrete bucket hanging from a crane
(it was flagged as "worker 921: no helmet, no vest, no boots"). A box is looked at again when the main model is unsure
about it, or when it holds a helmet-coloured blob much bigger than any helmet. Two other models then look for a body in it:
a pose model (needs several body points) and the general COCO person detector. If neither finds one, the box is an object.

In video a track is only declared an object after two checks agree, and it is released again as soon as two checks in a
row do find a body. Boxes too small to judge are left as people (they are handled elsewhere as "too small to check").
"""
from __future__ import annotations

from collections import deque
from pathlib import Path

import cv2
import numpy as np

from .types import Detection

ROOT = Path(__file__).resolve().parents[1]


def helmet_blob_ratio(crop_bgr) -> float:
    """Width of the largest orange / yellow / red blob, as a share of the crop's width.

    A real helmet is a small part of a person's width; a blob this wide is something big in a helmet colour.
    """
    if crop_bgr is None or crop_bgr.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    mask = (((h <= 35) | (h >= 170)) & (s > 110) & (v > 90)).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count <= 1:
        return 0.0
    widest = stats[1:, cv2.CC_STAT_WIDTH][np.argmax(stats[1:, cv2.CC_STAT_AREA])]
    return float(widest) / crop_bgr.shape[1]


class PersonVerifier:
    def __init__(self, pose_weights: str | None = None, coco_weights: str | None = None, device: str | None = None,
                 suspect_conf: float = 0.70, blob_ratio: float = 0.45, min_height: int = 80, min_width: int = 30,
                 min_keypoints: int = 4, votes_needed: int = 2, window: int = 5):
        self.pose_weights = pose_weights or str(ROOT / "yolo11n-pose.pt")
        self.coco_weights = coco_weights or str(ROOT / "yolo11s.pt")
        self.device = device
        self.suspect_conf, self.blob_ratio = suspect_conf, blob_ratio
        self.min_height, self.min_width, self.min_keypoints = min_height, min_width, min_keypoints
        self.votes_needed, self.window = votes_needed, window
        self._models: tuple | None = None
        self._votes: dict[int, deque] = {}
        self._latched: set[int] = set()

    def reset(self) -> None:
        """Forget every track's votes (call before a new video, because track numbers start again)."""
        self._votes.clear()
        self._latched.clear()

    # ---- the two other models (loaded the first time they are needed) -----------------------------
    def _load(self):
        if self._models is None:
            from ultralytics import YOLO

            self._models = (YOLO(self.pose_weights), YOLO(self.coco_weights))
        return self._models

    def _sees_person(self, crop) -> bool:
        pose, coco = self._load()
        result = pose(crop, imgsz=416, conf=0.25, verbose=False, device=self.device)[0]
        if len(result.boxes):
            points = result.keypoints.conf if result.keypoints is not None and result.keypoints.conf is not None else None
            for i, box in enumerate(result.boxes):
                visible = int((points[i] > 0.5).sum()) if points is not None else 0
                if visible >= self.min_keypoints or float(box.conf) >= 0.6:
                    return True
        return len(coco(crop, imgsz=416, classes=[0], conf=0.3, verbose=False, device=self.device)[0].boxes) > 0

    # ---- the decision ---------------------------------------------------------------------------
    def _is_object(self, image, det: Detection) -> bool:
        x1, y1, x2, y2 = det.box
        width, height = x2 - x1, y2 - y1
        if height < self.min_height or width < self.min_width:
            return False  # too small to judge: leave it as a person
        track = det.track_id
        latched = track in self._latched
        watched = latched or any(self._votes.get(track, ()))  # a track with an "object" vote keeps being checked
        pad = int(0.1 * max(width, height))
        crop = image[max(0, y1 - pad): y2 + pad, max(0, x1 - pad): x2 + pad]
        suspicious = watched or det.conf < self.suspect_conf or helmet_blob_ratio(image[y1:y2, x1:x2]) >= self.blob_ratio
        if not suspicious:
            return False
        sees = self._sees_person(crop)
        if track is None:  # a single photo: one check decides
            return not sees
        votes = self._votes.setdefault(track, deque(maxlen=self.window))
        votes.append(not sees)  # True means "looks like an object"
        if sees:
            if latched and len(votes) >= 2 and not votes[-1] and not votes[-2]:
                self._latched.discard(track)
        elif sum(votes) >= self.votes_needed:
            self._latched.add(track)
        return track in self._latched

    def screen(self, image, detections: list[Detection]) -> tuple[list[Detection], list[Detection]]:
        """Split detections into (kept, objects): objects are "person" boxes that turned out not to hold a person."""
        kept, objects = [], []
        for det in detections:
            (objects if det.label == "person" and self._is_object(image, det) else kept).append(det)
        return kept, objects
