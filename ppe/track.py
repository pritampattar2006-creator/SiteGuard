"""Video: follow each worker across frames and report a violation only once it is stable.

A single frame can flicker (a helmet detection drops below the threshold for a moment), so an alarm
is raised only when a worker is missing an item in `min_hits` of the last `window` usable frames.
"""
from __future__ import annotations

import csv
from collections import defaultdict, deque
from pathlib import Path

import cv2

from .annotate import crop_person, draw
from .lighting import is_backlit
from .config import Config
from .incident import FallMonitor
from .pipeline import analyze
from .types import MISSING, PRESENT, UNVERIFIABLE


class PersistenceFilter:
    """Confirms a (worker, item) violation after it persists, reports it once, re-arms when the item is seen."""

    def __init__(self, window: int, min_hits: int):
        self.window, self.min_hits = window, min_hits
        self._recent: dict[tuple[int, str], deque] = defaultdict(lambda: deque(maxlen=window))
        self._confirmed: set[tuple[int, str]] = set()

    def update(self, worker_id: int, item: str, state: str) -> bool:
        """Feed one observation. Returns True only on the frame a violation becomes confirmed."""
        key = (worker_id, item)
        if state == UNVERIFIABLE:  # tiny, cut off or crowded: no evidence either way, so skip the frame
            return False
        if state == PRESENT:  # seen wearing it: forget the history and allow a later re-report
            self._recent[key].clear()
            self._confirmed.discard(key)
            return False
        if state == MISSING:
            self._recent[key].append(True)
            if key not in self._confirmed and sum(self._recent[key]) >= self.min_hits:
                self._confirmed.add(key)
                return True
        return False


class _TrackingView:
    """Lets pipeline.analyze() use detector.track() where it normally calls detector.detect()."""

    def __init__(self, detector):
        self.detector = detector

    def detect(self, image, cfg):
        return self.detector.track(image, cfg)

    @property
    def last_objects(self):
        return getattr(self.detector, "last_objects", [])

    @property
    def dark(self):
        return getattr(self.detector, "dark", False)

    @dark.setter
    def dark(self, value):
        self.detector.dark = value


DOWN_BANNER_FRAMES = 120  # about 4 seconds of video
def _box_overlap_share(a, b) -> float:
    w, h = min(a[2], b[2]) - max(a[0], b[0]), min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0.0, w) * max(0.0, h)
    return inter / max(1.0, min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1])))


def stitch_tracks(tracks: dict, gap_frames: int) -> dict:
    """Which track numbers are really one person. `tracks` maps a number to {"first", "last", "first_box", "last_box"} (frame numbers and boxes).

    A tracker gives a person a new number when it loses them for a moment (hidden behind something, flickering detection, a shaking camera). Two numbers are
    one person when the second starts soon after the first ended, close to where it ended and about the same size, and the two numbers never appear in the
    same picture. Returns {number: the number it should be called}, only for numbers that change."""
    order = sorted(tracks, key=lambda i: tracks[i]["first"])
    spans = {i: [(tracks[i]["first"], tracks[i]["last"])] for i in order}  # root number -> the frame ranges of everyone merged into it
    root = {i: i for i in order}

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    def together(r1, r2):  # would merging put two people who are in the same picture under one number?
        return any(a0 <= b1 and b0 <= a1 for a0, a1 in spans[r1] for b0, b1 in spans[r2])

    for b in order:
        tb = tracks[b]
        h_b = tb["first_box"][3] - tb["first_box"][1]
        best, best_dist = None, None
        for a in order:
            ta = tracks[a]
            if a == b or not 0 < tb["first"] - ta["last"] <= gap_frames or find(a) == find(b):
                continue
            h_a = ta["last_box"][3] - ta["last_box"][1]
            if not 0.5 <= h_a / max(1.0, h_b) <= 2.0:
                continue  # not the same size: a different person
            ca = ((ta["last_box"][0] + ta["last_box"][2]) / 2, (ta["last_box"][1] + ta["last_box"][3]) / 2)
            cb = ((tb["first_box"][0] + tb["first_box"][2]) / 2, (tb["first_box"][1] + tb["first_box"][3]) / 2)
            dist = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
            near = dist <= 0.7 * max(h_a, h_b) or _box_overlap_share(ta["last_box"], tb["first_box"]) >= 0.3
            if near and not together(find(a), find(b)) and (best is None or dist < best_dist):
                best, best_dist = a, dist
        if best is not None:
            ra, rb = find(best), find(b)
            root[rb] = ra
            spans[ra] += spans.pop(rb)
    groups: dict = {}
    for i in order:
        groups.setdefault(find(i), []).append(i)
    return {i: min(ids) for ids in groups.values() for i in ids if i != min(ids)}


BACKLIT_SHARE = 0.3  # a person who was a silhouette in at least this share of their frames raises no gear incident


def draw_alert_banner(image, text: str) -> None:
    """A red bar across the top of the frame, so a worker-down alert cannot be missed when the annotated video is played."""
    height = max(36, image.shape[0] // 14)
    cv2.rectangle(image, (0, 0), (image.shape[1], height), (30, 30, 200), -1)
    scale = height / 48
    cv2.putText(image, text, (12, int(height * 0.7)), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), max(2, int(scale * 2)), cv2.LINE_AA)


def _open_writer(path, fps: float, size: tuple[int, int]):
    """H.264 first, because browsers can play it; plain MPEG-4 if this OpenCV build has no H.264 encoder."""
    for code in ("avc1", "mp4v"):
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*code), fps, size)
        if writer.isOpened():
            return writer
        writer.release()
    raise ValueError("Could not create the output video file.")


MAX_SIDE = 1920  # frames longer than this (a 4K phone clip is 3840) are scaled down once: the model looks at about 960 px anyway, and everything else is 4x cheaper


def fit_side(frame, limit: int = MAX_SIDE):
    """The frame scaled down so its longer side is at most `limit` (unchanged when it already is)."""
    h, w = frame.shape[:2]
    longest = max(h, w)
    if longest <= limit:
        return frame
    scale = limit / longest
    return cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)


def fitted_size(width: int, height: int, limit: int = MAX_SIDE) -> tuple[int, int]:
    """The (width, height) a frame of this size has after fit_side()."""
    longest = max(width, height)
    if longest <= limit:
        return width, height
    scale = limit / longest
    return max(1, int(width * scale)), max(1, int(height * scale))


def process_video(
    path: str | Path,
    cfg: Config,
    detector,
    out_video: str | Path,
    out_csv: str | Path,
    evidence_dir: str | Path,
    every_nth: int = 2,
    max_frames: int = 600,
    progress=None,
    fall_pose=None,
    hazard=None,
    welding=None,
    on_frame=None,
    identify=None,
    crosscheck=None,
    max_side: int = MAX_SIDE,
) -> list[dict]:
    """Annotate a clip, and write one CSV row (plus one evidence photo) per confirmed violation.

    `progress(frames_done, frames_total)` is called as frames are read, so a UI can show a progress bar.
    `on_frame(result, annotated, checked)` runs on every checked frame (it may draw on `annotated`); `identify(worker_id)` then says who a
    tracked worker is (an Identity or None), and that name goes into the incident rows.
    """
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    width, height = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = min(max_frames, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) or max_frames)
    writer = _open_writer(out_video, fps / every_nth, fitted_size(width, height, max_side))
    Path(evidence_dir).mkdir(parents=True, exist_ok=True)

    persistence = PersistenceFilter(cfg.persist_window, cfg.persist_min)
    monitor = FallMonitor(cfg)
    view = _TrackingView(detector)
    incidents: list[dict] = []
    frame_no = -1
    seen: dict[int, int] = {}  # frames each tracked person appeared in
    silhouette: dict[int, int] = {}  # and how many of those they were a dark silhouette against a bright background
    tracks: dict[int, dict] = {}  # where and when each track number was seen, so numbers that are really one person can be joined afterwards

    while frame_no + 1 < max_frames:
        if not capture.grab():  # a skipped frame is only taken off the stream, never converted to a picture
            break
        frame_no += 1
        if progress and total:
            progress(frame_no + 1, total)
        if frame_no % every_nth:
            continue
        ok, frame = capture.retrieve()
        if not ok:
            break
        frame = fit_side(frame, max_side)
        result = analyze(frame, cfg, view)
        if crosscheck is not None:  # a second model may hold back a helmet call before it is counted
            crosscheck(frame, result)
        annotated = draw(frame, result, show_unassigned=False)  # video shows people only
        for m in result.matches:
            t = tracks.setdefault(m.worker_id, {"first": frame_no, "first_box": tuple(m.person.box)})
            t["last"], t["last_box"] = frame_no, tuple(m.person.box)
        if on_frame is not None:
            on_frame(frame, result, annotated, frame_no // every_nth)
        for alert in (fall_pose.update(frame_no / fps, frame) if fall_pose is not None else []):  # learned fall detector (experimental)
            evidence = Path(evidence_dir) / f"ALERT_person{alert['worker_id']}_fallmodel_frame{frame_no}.jpg"
            cv2.imwrite(str(evidence), annotated)
            incidents.append({"time_s": alert["time_s"], "frame": frame_no, "worker_id": alert["worker_id"], "missing_item": "WORKER DOWN",
                              "evidence": evidence.name, "kind": "FALL_MODEL", "detail": alert["reason"]})
        for alert in (welding.update(frame_no / fps, frame, [tuple(p.box) for p in result.people]) if welding is not None else []):  # someone is welding
            x1, y1, x2, y2 = (int(v) for v in alert["box"])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 140, 255), 3)
            cv2.putText(annotated, "WELDING OR GRINDING SPARKS", (x1, max(18, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 140, 255), 2, cv2.LINE_AA)
            evidence = Path(evidence_dir) / f"welding_frame{frame_no}.jpg"
            cv2.imwrite(str(evidence), annotated)
            incidents.append({"time_s": alert["time_s"], "frame": frame_no, "worker_id": 0, "missing_item": "WELDING", "evidence": evidence.name,
                              "kind": "ACTIVITY", "detail": alert["reason"]})
        for alert in (hazard.update(frame_no / fps, frame, [tuple(p.box) for p in result.people]) if hazard is not None else []):  # an object dropping near or onto a worker
            x1, y1, x2, y2 = (int(v) for v in alert["box"])
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (30, 30, 200), 3)
            evidence = Path(evidence_dir) / f"ALERT_object_{alert['kind'].lower().replace(' ', '_')}_frame{frame_no}.jpg"
            cv2.imwrite(str(evidence), annotated)
            incidents.append({"time_s": alert["time_s"], "frame": frame_no, "worker_id": 0, "missing_item": alert["kind"], "evidence": evidence.name,
                              "kind": "HAZARD", "detail": alert["reason"], "alarm": alert["alarm"]})
        for alert in monitor.update(frame_no / fps, result.people):  # worker down: a fall or collapse that does not recover
            evidence = Path(evidence_dir) / f"ALERT_worker{alert['worker_id']}_{alert['kind'].lower()}_frame{frame_no}.jpg"
            cv2.imwrite(str(evidence), annotated)
            incidents.append({"time_s": alert["time_s"], "frame": frame_no, "worker_id": alert["worker_id"],
                              "missing_item": "WORKER DOWN", "evidence": evidence.name, "kind": alert["kind"], "detail": alert["reason"]})
        for match in result.matches:
            seen[match.worker_id] = seen.get(match.worker_id, 0) + 1
            if is_backlit(frame, match.person.box):
                silhouette[match.worker_id] = silhouette.get(match.worker_id, 0) + 1
        for verdict in result.verdicts:
            for item in cfg.required:
                state = verdict.helmet_state if item == "helmet" else verdict.vest_state
                backlit_person = silhouette.get(verdict.worker_id, 0) >= BACKLIT_SHARE * seen.get(verdict.worker_id, 1)
                if persistence.update(verdict.worker_id, item, state) and not backlit_person:  # a person who is mostly a silhouette cannot be judged
                    evidence = Path(evidence_dir) / f"worker{verdict.worker_id}_no_{item}_frame{frame_no}.jpg"
                    cv2.imwrite(str(evidence), annotated)
                    box = next((m.person.box for m in result.matches if m.worker_id == verdict.worker_id), None)
                    crop_name = ""
                    if box is not None:  # a close-up of just this worker, next to the whole picture
                        crop_name = evidence.stem + "_crop.jpg"
                        cv2.imwrite(str(Path(evidence_dir) / crop_name), crop_person(annotated, box))
                    incidents.append(
                        {"time_s": round(frame_no / fps, 2), "frame": frame_no, "worker_id": verdict.worker_id,
                         "missing_item": item, "evidence": evidence.name, "crop": crop_name, "kind": "PPE", "detail": verdict.reason}
                    )
        banner = next((i for i in reversed(incidents[-8:]) if (i["missing_item"] == "WORKER DOWN" or i.get("alarm")) and frame_no - i["frame"] <= DOWN_BANNER_FRAMES), None)
        if banner is not None:
            draw_alert_banner(annotated, "ACCIDENT ALERT: WORKER DOWN" if banner["missing_item"] == "WORKER DOWN" else f"DANGER: {banner['missing_item']}")  # shown for a few seconds of video after the alert
        writer.write(annotated)
    capture.release()
    writer.release()
    same = stitch_tracks(tracks, gap_frames=int(3 * fps))
    if same:  # one person who got a new number after being lost keeps one number, and is counted once per missing item
        kept, seen_rows = [], set()
        for row in incidents:
            row["worker_id"] = same.get(row["worker_id"], row["worker_id"])
            key = (row["worker_id"], row["missing_item"])
            if row["kind"] == "PPE" and key in seen_rows:
                continue
            seen_rows.add(key)
            kept.append(row)
        incidents = kept
    if identify is not None:  # name each incident by the person it ended up being, so track-number changes do not split one person
        for row in incidents:
            who = identify(row["worker_id"])
            row["person"], row["person_id"] = (who.name, who.employee_id) if who else ("", "")

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["time_s", "frame", "worker_id", "missing_item", "evidence", "crop", "kind", "detail", "person", "person_id"], restval="", extrasaction="ignore")
        writer_csv.writeheader()
        writer_csv.writerows(incidents)
    return incidents


TrackingView = _TrackingView  # public name, used by the live camera
