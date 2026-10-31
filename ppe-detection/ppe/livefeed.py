"""A live camera on the same network (a phone running an IP-camera app, or a CCTV camera), watched by the detector.

The phone shares its camera as a web address (for example http://192.168.1.5:8080/video, or rtsp://...). This reads that stream in one thread (always
keeping only the newest frame, so the picture never lags behind) and, in another, checks the newest frame about once a second with the same analysis as
an uploaded photo. The result is kept as a JPEG that the desk shows as a live picture, and the people caught are sent on by the analysis itself.

Only addresses on the local network are accepted: this service must not be usable to reach out to other machines on the internet.
"""
from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
import urllib.parse
import uuid

import cv2


def normalise_address(url: str) -> str:
    """Fix the slips people make typing a camera address: a missing http://, a dot instead of the colon before the port (192.168.1.5.8080),
    https:// for a camera on the local network (they have no real certificate; the apps serve plain http), and a missing /video on an http address."""
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    scheme, rest = url.split("://", 1)
    host_port, slash, path = rest.partition("/")
    if re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}\.\d{2,5}", host_port):  # 192.168.1.5.8080 -> 192.168.1.5:8080
        host_port = host_port.rsplit(".", 1)[0] + ":" + host_port.rsplit(".", 1)[1]
    host = host_port.split(":")[0]
    if scheme == "https" and re.fullmatch(r"(10|192\.168|172\.(1[6-9]|2\d|3[01]))\..*", host):
        scheme = "http"
    if scheme in ("http", "https") and path in ("",):
        path = "video"  # the address an IP-camera app serves its live picture on
    return f"{scheme}://{host_port}/{path}"


def check_address(url: str) -> str:
    """Raise ValueError unless this is an http, https or rtsp address on the local network (or this computer)."""
    parts = urllib.parse.urlparse(url.strip())
    if parts.scheme not in ("http", "https", "rtsp") or not parts.hostname:
        raise ValueError("Enter the camera address, for example http://192.168.1.5:8080/video")
    try:
        ip = ipaddress.ip_address(parts.hostname)
    except ValueError:
        try:
            ip = ipaddress.ip_address(socket.gethostbyname(parts.hostname))
        except OSError:
            raise ValueError("That camera address cannot be found on this network.") from None
    if not (ip.is_private or ip.is_loopback or ip.is_link_local):
        raise ValueError("Only cameras on your own WiFi or network are allowed.")
    return url.strip()


SHOW_EVERY_S = 1 / 15  # the picture is refreshed about 15 times a second
OVERLAY_LIFE_S = 4.0  # boxes from a check older than this are not drawn any more
MAX_WIDTH = 1280


def fit_width(frame, width: int = MAX_WIDTH):
    """A phone may send 1920 wide; the detector and the picture use at most 1280 (no loss for finding people, less to carry around)."""
    if frame.shape[1] <= width:
        return frame
    return cv2.resize(frame, (width, max(1, int(frame.shape[0] * width / frame.shape[1]))), interpolation=cv2.INTER_AREA)


def make_overlay(frame, annotated):
    """Everything the detector drew (boxes, names, the top bar) as (a yes/no mask, the drawn picture), so it can be put on later frames."""
    if frame.shape != annotated.shape:
        return None
    return cv2.absdiff(annotated, frame).max(axis=2) > 6, annotated


def compose(frame, overlay):
    """A fresh frame with the latest detections drawn on it (unchanged if there are none, or the picture size changed)."""
    if overlay is None or overlay[0].shape != frame.shape[:2]:
        return frame
    shown = frame.copy()
    shown[overlay[0]] = overlay[1][overlay[0]]
    return shown


ROTATIONS = (0, 90, 180, 270)  # degrees clockwise applied to the camera's own frame
_CV_ROTATE = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
ORIENT_EVERY_S = 1.5  # how often the picture's orientation is re-checked
ORIENT_FAST_S = 0.4  # ... and how often during the first few checks after connecting
ORIENT_VOTES = 2  # a new orientation must win this many checks in a row before the picture turns (so it never flips back and forth)


def rotate_frame(frame, degrees: int):
    """The frame turned clockwise by 0, 90, 180 or 270 degrees."""
    return frame if degrees % 360 == 0 else cv2.rotate(frame, _CV_ROTATE[degrees % 360])


def upright_count(keypoints, confidences) -> int:
    """How many people stand head-up in one picture. keypoints (n, 17, 2) and confidences (n, 17) are a pose model's output.

    A person is upright when the line from the hips to the shoulders points up the picture and is more vertical than sideways. When the hips are out of
    view, the line from the shoulders to the nose is used instead. A phone held upright streams its picture on its side, so there everybody lies down."""
    count = 0
    for kp, kc in zip(keypoints, confidences):
        sho = [kp[i] for i in (5, 6) if kc[i] >= 0.4]
        hip = [kp[i] for i in (11, 12) if kc[i] >= 0.4]
        if not sho:
            continue
        top = (sum(q[0] for q in sho) / len(sho), sum(q[1] for q in sho) / len(sho))
        if hip:
            base = (sum(q[0] for q in hip) / len(hip), sum(q[1] for q in hip) / len(hip))
            dx, dy = top[0] - base[0], top[1] - base[1]
        elif kc[0] >= 0.4:
            dx, dy = kp[0][0] - top[0], kp[0][1] - top[1]  # nose relative to the shoulders
        else:
            continue
        if dy < 0 and abs(dy) > 1.2 * abs(dx):
            count += 1
    return count


def pick_rotation(scores: dict, current: int):
    """The rotation with clearly the most upright people. None when nobody was seen or the best turns are tied and the current one is not among them."""
    best = max(scores.values(), default=0)
    if best == 0:
        return None
    winners = [d for d, s in scores.items() if s == best]
    if current in winners:
        return current  # ties are decided in favour of the picture as it is
    return winners[0] if len(winners) == 1 else None


class LiveFeeds:
    def __init__(self, analyse, every_s: float = 1.0):
        self._analyse = analyse  # (frame, options) -> dict with workers, pushed, repeats and "_image" (the annotated picture)
        self.every_s = every_s
        self._feeds: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._pose = None  # a small pose model, loaded the first time a camera needs its orientation checked
        self._pose_lock = threading.Lock()

    def start(self, url: str, options: dict) -> str:
        url = check_address(normalise_address(url))
        self.stop_sector(options.get("sector", ""))  # one camera per sector: a new one replaces that sector's old one, and other sectors keep theirs
        feed_id = uuid.uuid4().hex[:10]
        auto = str(options.get("rotate", "auto")).lower() == "auto"
        fixed = 0 if auto else (int(options["rotate"]) % 360 if int(options["rotate"]) % 360 in ROTATIONS else 0)
        feed = {"id": feed_id, "url": url, "options": options, "status": "connecting", "error": "", "latest": None, "jpg": b"", "stop": threading.Event(),
                "rotate": fixed, "autoRotate": auto, "orientVotes": [], "orienting": False, "orientAt": 0.0, "orientChecks": 0, "analysed": 0, "overlay": None, "workers": [], "pushed": 0, "repeats": 0, "lastAt": 0.0, "frames": 0, "startedAt": time.time()}
        with self._lock:
            self._feeds[feed_id] = feed
        threading.Thread(target=self._read, args=(feed,), daemon=True).start()
        threading.Thread(target=self._watch, args=(feed,), daemon=True).start()
        return feed_id

    def stop_sector(self, sector: str) -> None:
        with self._lock:
            for feed in self._feeds.values():
                if feed["options"].get("sector", "") == sector and not feed["stop"].is_set():
                    feed["stop"].set()
                    if feed["status"] != "error":
                        feed["status"] = "stopped"

    def running(self, sectors: set[str] | None = None) -> list[dict]:
        """The cameras that are on (or have failed and not been replaced), newest first, optionally only those of the given sectors."""
        found = [f for f in self._feeds.values() if f["status"] != "stopped" and (sectors is None or f["options"].get("sector", "") in sectors)]
        return [self.status(f["id"]) for f in sorted(found, key=lambda f: -f["startedAt"])]

    def stop_all(self) -> None:
        with self._lock:
            for feed in self._feeds.values():
                feed["stop"].set()
                if feed["status"] != "error":
                    feed["status"] = "stopped"

    def stop(self, feed_id: str) -> bool:
        feed = self._feeds.get(feed_id)
        if not feed:
            return False
        feed["stop"].set()
        feed["status"] = "stopped"
        return True

    def rotate(self, feed_id: str, degrees=None, auto: bool = False):
        """Turn the picture by hand (clockwise, added to what it is now), or give the choice back to the automatic check."""
        feed = self._feeds.get(feed_id)
        if not feed:
            return None
        if auto:
            feed.update(autoRotate=True, orientVotes=[], orientChecks=0)
        else:
            feed.update(autoRotate=False, rotate=(feed["rotate"] + int(degrees or 90)) % 360)
        feed["overlay"] = None  # boxes drawn for the old orientation must not be laid over the new picture
        return self.status(feed_id)

    def _orient_job(self, feed: dict, raw) -> None:
        try:
            self._check_orientation(feed, raw)
        except Exception as problem:  # the orientation check is a convenience: the picture keeps flowing without it
            feed["error"] = str(problem)[:200]
        finally:
            feed["orienting"] = False

    def _check_orientation(self, feed: dict, raw) -> None:
        """Try the four turns of this frame, count the people standing head-up in each, and switch only after the same winner twice in a row."""
        if self._pose is None:
            with self._pose_lock:
                if self._pose is None:
                    from ultralytics import YOLO

                    from .verify import ROOT

                    self._pose = YOLO(str(next(p for p in (ROOT / "weights" / "yolo11n-pose.pt", ROOT / "yolo11n-pose.pt") if p.exists())))
        small = fit_width(raw, 640)
        turned = [rotate_frame(small, d) for d in ROTATIONS]
        with self._pose_lock:
            results = self._pose(turned, imgsz=640, conf=0.3, verbose=False)
        scores = {d: (upright_count(r.keypoints.xy.cpu().numpy(), r.keypoints.conf.cpu().numpy()) if r.keypoints is not None else 0) for d, r in zip(ROTATIONS, results)}
        feed["orientChecks"] += 1
        winner = pick_rotation(scores, feed["rotate"])
        votes = feed["orientVotes"]
        votes.append(winner)
        del votes[:-ORIENT_VOTES]
        if winner is not None and winner != feed["rotate"] and len(votes) == ORIENT_VOTES and all(v == winner for v in votes):
            feed.update(rotate=winner, overlay=None, orientVotes=[])

    def jpg(self, feed_id: str) -> bytes | None:
        feed = self._feeds.get(feed_id)
        return feed["jpg"] if feed else None

    def status(self, feed_id: str) -> dict | None:
        feed = self._feeds.get(feed_id)
        if not feed:
            return None
        return {"id": feed["id"], "url": feed["url"], "sector": feed["options"].get("sector", ""), "location": feed["options"].get("location", ""), "startedAt": feed["startedAt"], "status": feed["status"], "error": feed["error"], "analysed": feed["analysed"], "workers": feed["workers"], "pushed": feed["pushed"],
                "repeats": feed["repeats"], "frames": feed["frames"], "rotation": feed["rotate"], "autoRotate": feed["autoRotate"], "secondsSinceCheck": round(time.time() - feed["lastAt"], 1) if feed["lastAt"] else None}

    # ---- threads ----
    def _read(self, feed: dict) -> None:
        """Keeps up with the camera: every frame is taken off the stream (so nothing queues up and the picture is never behind), about 15 a second are
        converted and shown, and the newest detections are drawn on top of them."""
        capture, failures, last_show = None, 0, 0.0
        while not feed["stop"].is_set():
            if capture is None:
                capture = cv2.VideoCapture(feed["url"])
                if not capture.isOpened():
                    capture.release(); capture = None; failures += 1
                    if failures >= 4:
                        feed.update(status="error", error="Could not open the camera. Check the address, that the phone app is running, and that both are on the same WiFi.")
                        feed["stop"].set()
                        return
                    time.sleep(1.5)
                    continue
                try:
                    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # no queue of old frames
                except Exception:
                    pass
            if not capture.grab():
                capture.release(); capture = None; failures += 1
                if failures >= 8:
                    feed.update(status="error", error="The camera stream stopped.")
                    feed["stop"].set()
                    return
                time.sleep(0.5)
                continue
            failures = 0
            now = time.time()
            if now - last_show < SHOW_EVERY_S:
                continue  # taken off the stream but not converted: keeps the picture current without the cost
            ok, frame = capture.retrieve()
            if not ok:
                continue
            last_show = now
            if feed["autoRotate"] and not feed["orienting"] and now - feed["orientAt"] >= (ORIENT_FAST_S if feed["orientChecks"] < 4 else ORIENT_EVERY_S):
                feed["orientAt"], feed["orienting"] = now, True
                threading.Thread(target=self._orient_job, args=(feed, frame.copy()), daemon=True).start()  # apart from the picture: loading the model must never hold it up
            frame = fit_width(rotate_frame(frame, feed["rotate"]))
            feed["latest"] = frame
            feed["frames"] += 1
            if feed["status"] == "connecting":
                feed["status"] = "live"
            overlay = feed["overlay"] if now - feed["lastAt"] < OVERLAY_LIFE_S else None  # old boxes are not left hanging if checking stalls
            feed["jpg"] = cv2.imencode(".jpg", compose(frame, overlay), [cv2.IMWRITE_JPEG_QUALITY, 78])[1].tobytes()
        if capture is not None:
            capture.release()

    def _watch(self, feed: dict) -> None:
        """Checks the newest frame about once a second (it takes a moment, so it runs apart from the picture) and keeps what it drew for the picture."""
        last_frame_count = -1
        while not feed["stop"].is_set():
            frame = feed["latest"]
            if frame is None or feed["frames"] == last_frame_count:
                time.sleep(0.05)
                continue
            last_frame_count = feed["frames"]
            started = time.time()
            try:
                out = self._analyse(frame.copy(), feed["options"])
                annotated = out.pop("_image")
                feed["overlay"] = make_overlay(frame, annotated)
                feed.update(workers=out["workers"], pushed=feed["pushed"] + int(out.get("pushed", 0)), repeats=feed["repeats"] + int(out.get("repeats", 0)),
                            analysed=feed["analysed"] + 1, lastAt=time.time())
            except Exception as problem:  # one bad frame must not end the watch
                feed["error"] = str(problem)[:200]
            time.sleep(max(0.0, self.every_s - (time.time() - started)))
