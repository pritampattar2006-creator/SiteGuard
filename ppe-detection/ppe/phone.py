"""Phone-use watch: is a worker holding a phone, or talking on one?

There is no model trained on construction workers using phones, so this combines two generic models: a pose model (where each person's wrists, elbows,
ears and shoulders are) and a standard object model that knows the class "cell phone". The rules are plain geometry on those outputs:

  CALL           a phone is at the hand AND that hand is raised to the head (talking on the phone)
  PHONE_IN_HAND  a phone is at the hand, hand not at the head (reading or typing)
  POSSIBLE_CALL  no phone seen, but a hand is raised to the ear with the elbow bent (a phone is small and often hidden by the hand)

It is only a prompt for a person to look, never a violation or a penalty. Limits: phones are tiny in wide shots and are often missed; scratching the head,
wiping sweat, drinking or wearing a headset can look like POSSIBLE_CALL, which is why that one is the weakest. Accuracy has not been measured on real
footage: there is no labelled set of phone-use photos here. Only the geometry is tested, with hand-made points.
"""
from __future__ import annotations

import math
from collections import deque

from .types import Box

# COCO pose joints
NOSE, L_EYE, R_EYE, L_EAR, R_EAR, L_SHO, R_SHO, L_ELB, R_ELB, L_WRI, R_WRI = range(11)
MIN_JOINT_CONF = 0.4
CALL, PHONE_IN_HAND, POSSIBLE_CALL = "CALL", "PHONE_IN_HAND", "POSSIBLE_CALL"
PHONE_AT_HAND = 0.9  # a phone this close to a wrist (in head-widths) is "in the hand"
HEAD_PHONE = 1.1  # a phone this close to the middle of the face (in head-widths) is held against the head
HAND_AT_HEAD = 1.3  # a wrist this close to an ear (in head-widths) is "at the head"
MIN_PERSON_HEIGHT = 80  # px: smaller people have joints too coarse to judge


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _centre(box: Box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def head_width(kp, kc) -> float | None:
    """Ear-to-ear (or eye-to-eye, doubled) distance: the ruler used for every other distance, so the rules work at any size."""
    if kc[L_EAR] >= MIN_JOINT_CONF and kc[R_EAR] >= MIN_JOINT_CONF:
        return max(_dist(kp[L_EAR], kp[R_EAR]), 8.0)
    if kc[L_EYE] >= MIN_JOINT_CONF and kc[R_EYE] >= MIN_JOINT_CONF:
        return max(2.0 * _dist(kp[L_EYE], kp[R_EYE]), 8.0)
    if kc[L_SHO] >= MIN_JOINT_CONF and kc[R_SHO] >= MIN_JOINT_CONF:
        return max(0.6 * _dist(kp[L_SHO], kp[R_SHO]), 8.0)  # the head is roughly 0.6 of the shoulder width
    return None


MIN_RULER_FRAC = 0.10  # a head is about a tenth of a person's height; a tilted-down head makes ear-to-ear look much narrower than it is


def head_centre(kp, kc):
    """The middle of the visible face points (nose, eyes, ears): works when the head is in profile and one ear is hidden."""
    pts = [kp[i] for i in (NOSE, L_EYE, R_EYE, L_EAR, R_EAR) if kc[i] >= MIN_JOINT_CONF]
    return (sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts)) if pts else None


def ruler_for(person_box: Box, kp, kc) -> float | None:
    """The head-width ruler, never smaller than a tenth of the person's height (so a bowed head does not shrink every distance limit)."""
    ruler = head_width(kp, kc)
    return None if ruler is None else max(ruler, MIN_RULER_FRAC * (person_box[3] - person_box[1]))


def phone_use(person_box: Box, kp, kc, phones: list[Box]) -> dict | None:
    """Judge one person from their pose points (17 x 2), joint confidences (17) and the phone boxes seen in the picture. None = nothing to report."""
    if person_box[3] - person_box[1] < MIN_PERSON_HEIGHT:
        return None
    ruler = ruler_for(person_box, kp, kc)
    if ruler is None:
        return None
    best = None
    face = head_centre(kp, kc)
    phone_at_face = face is not None and any(_dist(face, _centre(p)) <= HEAD_PHONE * ruler + max(p[2] - p[0], p[3] - p[1]) / 2 for p in phones)
    for wrist, elbow, ear, shoulder in ((L_WRI, L_ELB, L_EAR, L_SHO), (R_WRI, R_ELB, R_EAR, R_SHO)):
        if kc[wrist] < MIN_JOINT_CONF:
            continue
        w = kp[wrist]
        near_phone = any(_dist(w, _centre(p)) <= PHONE_AT_HAND * ruler + max(p[2] - p[0], p[3] - p[1]) / 2 for p in phones)
        at_head = False
        if kc[ear] >= MIN_JOINT_CONF or face is not None:
            shoulder_ok = kc[shoulder] >= MIN_JOINT_CONF
            raised = not shoulder_ok or w[1] < kp[shoulder][1]  # the hand is above the shoulder line (image y grows downward)
            bent = not (shoulder_ok and kc[elbow] >= MIN_JOINT_CONF) or _dist(w, kp[shoulder]) < 1.6 * _dist(kp[elbow], kp[shoulder])  # a bent arm brings the hand close to the shoulder
            targets = ([kp[ear]] if kc[ear] >= MIN_JOINT_CONF else []) + ([face] if face is not None else [])
            at_head = raised and bent and min(_dist(w, q) for q in targets) <= HAND_AT_HEAD * ruler
        if near_phone and at_head:
            kind, rank = CALL, 3
        elif near_phone:
            kind, rank = PHONE_IN_HAND, 2
        elif at_head:
            kind, rank = POSSIBLE_CALL, 1
        else:
            continue
        if best is None or rank > best[1]:
            best = (kind, rank, "left" if wrist == L_WRI else "right")
    if phone_at_face and (best is None or best[1] < 3):  # a phone held against the face is a call even when the hand is hidden or the ear is turned away
        best = (CALL, 3, best[2] if best else "")
    if best is None:
        return None
    kind, _, side = best
    side = f"{side} hand" if side else "hand"
    words = {CALL: f"A phone is at the head ({side}): talking on the phone.",
             PHONE_IN_HAND: f"A phone is in the {side}.",
             POSSIBLE_CALL: f"The {side} is raised to the ear with no phone seen. It may be a call, or only a gesture. Needs a look."}
    return {"kind": kind, "reason": words[kind], "needs_review": kind == POSSIBLE_CALL}


class PhoneMonitor:
    """Photo or video. For video, alert only when the same tracked person shows phone use in most of the last few checks, so one frame cannot raise it."""

    def __init__(self, pose_weights: str, object_weights: str, device: str | None = None, window: int = 5, need: int = 3, release: int = 1, cooldown_s: float = 20.0,
                 phone_conf: float = 0.2, hand_phone_conf: float = 0.3):
        from ultralytics import YOLO

        self.pose, self.objects, self.device = YOLO(pose_weights), YOLO(object_weights), device
        self.phone_id = next(i for i, n in self.objects.names.items() if n == "cell phone")
        self.window, self.need, self.cooldown, self.phone_conf, self.hand_phone_conf = window, need, cooldown_s, phone_conf, hand_phone_conf
        self.release, self.smooth = release, 0.5
        self._hist: dict[int, deque] = {}
        self._alerted: dict[int, float] = {}
        self._on: set[int] = set()  # people whose alert is showing: on after `need` hits, off only when hits fall to `release` (no flicker in between)
        self._last: dict[int, dict] = {}  # each person's latest finding, with a smoothed box

    def reset(self) -> None:
        """Forget everyone (call between clips)."""
        self._hist.clear(), self._alerted.clear(), self._on.clear(), self._last.clear()
        self.latest = {}

    def _phones_at_hands(self, frame_bgr, res) -> list[Box]:
        """Look for phones in a zoomed crop around every confident wrist. All crops go to the model in ONE call (one call per wrist was the slow part)."""
        height, width = frame_bgr.shape[:2]
        crops, origins = [], []
        for kp, kc, box in zip(res.keypoints.xy.cpu().numpy(), res.keypoints.conf.cpu().numpy(), res.boxes.xyxy.cpu().numpy()):
            ruler = ruler_for(tuple(box), kp, kc)
            if ruler is None or box[3] - box[1] < MIN_PERSON_HEIGHT:
                continue
            for wrist in (L_WRI, R_WRI):
                if kc[wrist] < MIN_JOINT_CONF:
                    continue
                half = int(max(3.0 * ruler, 96))
                cx, cy = int(kp[wrist][0]), int(kp[wrist][1])
                x1, y1, x2, y2 = max(0, cx - half), max(0, cy - half), min(width, cx + half), min(height, cy + half)
                if x2 > x1 and y2 > y1:
                    crops.append(frame_bgr[y1:y2, x1:x2])
                    origins.append((x1, y1))
        if not crops:
            return []
        found: list[Box] = []
        for seen, (x1, y1) in zip(self.objects(crops, classes=[self.phone_id], conf=self.hand_phone_conf, imgsz=320, device=self.device, verbose=False), origins):
            found += [(int(b[0]) + x1, int(b[1]) + y1, int(b[2]) + x1, int(b[3]) + y1) for b in seen.boxes.xyxy.cpu().numpy()]
        return found

    def look(self, frame_bgr, track: bool = False) -> list[dict]:
        """One frame -> a finding for each person who shows phone use (each carries 'box', 'kind', 'reason', 'worker_id' when tracked)."""
        pose_kw = dict(conf=0.3, imgsz=960, device=self.device, verbose=False)
        res = (self.pose.track(frame_bgr, persist=True, **pose_kw) if track else self.pose(frame_bgr, **pose_kw))[0]
        obj = self.objects(frame_bgr, classes=[self.phone_id], conf=self.phone_conf, imgsz=960, device=self.device, verbose=False)[0]
        phones = [tuple(int(v) for v in b) for b in obj.boxes.xyxy.cpu().numpy()]
        if res.keypoints is None:
            return []
        phones += self._phones_at_hands(frame_bgr, res)  # phones are tiny: a zoomed look around each wrist finds many the whole-picture pass misses
        ids = res.boxes.id.int().tolist() if track and res.boxes.id is not None else [None] * len(res.boxes)
        found = []
        for kp, kc, box, tid in zip(res.keypoints.xy.cpu().numpy(), res.keypoints.conf.cpu().numpy(), res.boxes.xyxy.cpu().numpy(), ids):
            box = tuple(int(v) for v in box)
            verdict = phone_use(box, kp, kc, phones)
            if verdict:
                found.append({**verdict, "box": box, "worker_id": tid, "phones": phones})
        return found

    def active(self) -> list[dict]:
        """Findings for people whose phone use is currently holding (smoothed boxes). Used to draw only confirmed ones, steadily."""
        return [self._last[tid] for tid in self._on if tid in self._last]

    def update(self, t: float, frame_bgr) -> list[dict]:
        """Video: feed frames in order; returns alerts for people who kept using a phone."""
        findings = {f["worker_id"]: f for f in self.look(frame_bgr, track=True) if f["worker_id"] is not None}
        self.latest = findings
        for tid, f in findings.items():  # smooth the box so it glides instead of jumping between looks
            old = self._last.get(tid)
            box = f["box"] if old is None else tuple(int(self.smooth * n + (1 - self.smooth) * o) for n, o in zip(f["box"], old["box"]))
            self._last[tid] = {**f, "box": box}
        alerts = []
        for tid in set(findings) | set(self._hist):
            hist = self._hist.setdefault(tid, deque(maxlen=self.window))
            hist.append(findings[tid]["kind"] if tid in findings else None)
            hits = [k for k in hist if k]
            if len(hits) >= self.need:
                self._on.add(tid)
            elif len(hits) <= self.release:
                self._on.discard(tid)
            if not hits and len(hist) == self.window:  # long gone: forget them
                for store in (self._hist, self._last, self._alerted):
                    store.pop(tid, None)
                continue
            if len(hits) >= self.need and t - self._alerted.get(tid, -1e9) >= self.cooldown:
                self._alerted[tid] = t
                kind = CALL if CALL in hits else PHONE_IN_HAND if PHONE_IN_HAND in hits else POSSIBLE_CALL
                alerts.append({"time_s": round(t, 2), "worker_id": tid, "kind": kind if kind.startswith("PHONE") else "PHONE_" + kind, "needs_review": kind == POSSIBLE_CALL,
                               "reason": findings[tid]["reason"] if tid in findings else "Phone use was seen a moment ago."})
        return alerts


LABELS = {CALL: "ON PHONE", PHONE_IN_HAND: "PHONE IN HAND", POSSIBLE_CALL: "PHONE? CHECK"}
RED, AMBER = (46, 51, 209), (0, 138, 217)  # BGR, same reds and ambers as the rest of the app
MIN_GUESS_HEIGHT = 150  # px: a raised hand with no phone seen is only drawn for people at least this tall (smaller ones are too coarse; one small worker at 100 px was a false alarm)


def draw_findings(frame_bgr, findings: list[dict], show_guesses: bool = True):
    """A copy of the picture with ONE box and ONE short label per person (no phone box, no names, no ids). Guesses (no phone seen) are drawn amber, and only for people tall enough to judge."""
    import cv2

    out = frame_bgr.copy()
    for f in findings:
        if f["needs_review"] and (not show_guesses or f["box"][3] - f["box"][1] < MIN_GUESS_HEIGHT):
            continue
        x1, y1, x2, y2 = f["box"]
        colour = AMBER if f["needs_review"] else RED
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 3)
        label = LABELS[f["kind"]]
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        top = max(0, y1 - th - 12)
        cv2.rectangle(out, (x1, top), (x1 + tw + 12, top + th + 12), colour, -1)
        cv2.putText(out, label, (x1 + 6, top + th + 3), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return out
