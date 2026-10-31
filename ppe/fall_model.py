"""A learned fall detector that works on body-pose features, as a second opinion beside the box-shape check in incident.py.

How it works: a pose model finds each person's body joints; per frame we keep a few numbers (torso tilt, body width against height,
head and hip height); over a 1.5 s window we measure how those changed; a small logistic-regression model, trained on the public GMDCSA24
dataset (acted indoor falls, MIT licence), turns the window into a "fall pattern" score.

Limits: it learned from acted falls in a few rooms with 4 people. It can raise false alarms (sitting down fast, lying down on purpose) and will
miss falls that look different on a real site. It says "a fall pattern was seen", never why. Treat an alert as "someone should check".
"""
from __future__ import annotations

import json
import math
from collections import deque
from pathlib import Path

import numpy as np

WINDOW = 15  # frames at about 10 per second = 1.5 s
SAMPLE_GAP_S = 0.09  # frames are resampled to about 10 per second, whatever the video's frame rate
FEATURES = ["torso_last", "torso_mean", "torso_range", "aspect_last", "aspect_mean", "aspect_change", "hip_drop", "head_drop",
            "hip_speed", "aspect_speed", "head_hip_last", "height_change"]


def frame_features(kps: np.ndarray, conf: np.ndarray, box: np.ndarray, frame_h: int):
    """kps: 17x2 pixel joints, conf: 17 scores, box: x1,y1,x2,y2. None if the body is too hidden to measure."""
    def mid(i, j):
        pts = [kps[k] for k in (i, j) if conf[k] > 0.3]
        return np.mean(pts, axis=0) if pts else None

    shoulders, hips = mid(5, 6), mid(11, 12)
    x1, y1, x2, y2 = box
    w, h = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
    if shoulders is None or hips is None:
        return None
    angle = math.degrees(math.atan2(abs(hips[0] - shoulders[0]), abs(hips[1] - shoulders[1]) + 1e-6))  # 0 = upright, 90 = horizontal
    head = kps[0] if conf[0] > 0.3 else shoulders
    return {"torso_angle": angle, "aspect": w / h, "hip_y": hips[1] / frame_h, "head_y": head[1] / frame_h,
            "head_hip": (hips[1] - head[1]) / h, "height": h / frame_h}


def window_features(torso, aspect, hip, head, head_hip, height) -> list[float]:
    """The 12 numbers that describe how the body moved over one window (each argument is a sequence of WINDOW values)."""
    torso, aspect, hip, head, head_hip, height = (np.asarray(a, dtype=float) for a in (torso, aspect, hip, head, head_hip, height))
    return [torso[-1], torso.mean(), torso.max() - torso.min(), aspect[-1], aspect.mean(), aspect[-1] - aspect[0], hip[-1] - hip[0],
            head[-1] - head[0], np.abs(np.diff(hip)).max(), np.abs(np.diff(aspect)).max(), head_hip[-1], height[-1] - height[0]]


class FallClassifier:
    def __init__(self, spec: dict):
        self.mean, self.scale = np.asarray(spec["mean"]), np.asarray(spec["scale"])
        self.coef, self.intercept = np.asarray(spec["coef"]), float(spec["intercept"])
        self.threshold = float(spec.get("threshold", 0.9))

    @classmethod
    def load(cls, path: str | Path) -> "FallClassifier":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def score(self, feats: list[float]) -> float:
        z = float(((np.asarray(feats) - self.mean) / self.scale) @ self.coef + self.intercept)
        return 1.0 / (1.0 + math.exp(-z))


class PoseFallMonitor:
    """Feed it video frames; it returns an alert when a tracked person's last 1.5 s looks like a fall."""

    def __init__(self, pose_weights: str, classifier: FallClassifier, device: str | None = None, cooldown_s: float = 10.0):
        from ultralytics import YOLO

        self.model, self.classifier, self.device, self.cooldown = YOLO(pose_weights), classifier, device, cooldown_s
        self._hist: dict[int, deque] = {}
        self._last_t: dict[int, float] = {}
        self._alerted: dict[int, float] = {}

    def update(self, t: float, frame_bgr) -> list[dict]:
        res = self.model.track(frame_bgr, persist=True, conf=0.3, imgsz=640, device=self.device, verbose=False)[0]
        if res.keypoints is None or res.boxes.id is None:
            return []
        alerts = []
        for kp, kc, box, tid in zip(res.keypoints.xy.cpu().numpy(), res.keypoints.conf.cpu().numpy(), res.boxes.xyxy.cpu().numpy(), res.boxes.id.int().tolist()):
            if t - self._last_t.get(tid, -1.0) < SAMPLE_GAP_S:
                continue
            feats = frame_features(kp, kc, box, frame_bgr.shape[0])
            if feats is None:
                continue
            self._last_t[tid] = t
            hist = self._hist.setdefault(tid, deque(maxlen=WINDOW))
            hist.append(feats)
            if len(hist) < WINDOW or t - self._alerted.get(tid, -1e9) < self.cooldown:
                continue
            cols = [[f[k] for f in hist] for k in ("torso_angle", "aspect", "hip_y", "head_y", "head_hip", "height")]
            score = self.classifier.score(window_features(*cols))
            if score >= self.classifier.threshold:
                self._alerted[tid] = t
                alerts.append({"time_s": round(t, 2), "worker_id": tid, "kind": "FALL_MODEL",
                               "reason": f"A fall pattern was seen (score {score:.2f}). Someone should check on them."})
        return alerts
