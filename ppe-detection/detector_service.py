"""A small local web service around the detector, for the websites' Feed page and face enrolment.

    python detector_service.py            # listens on http://localhost:5000

POST /analyze  {"image": "<data URL or base64>", "location": "Gate 2", "required": ["helmet", "vest"], "push": false}
  -> {"annotated": "<data URL>", "workers": [...], "pushed": 0}
  Each worker may carry "identity": a face-match SUGGESTION (name, role, department, score) when that face was enrolled.
  With "push": true, every worker the detector flagged is sent to the SiteGuard API as "Pending review", with the
  suggestion attached. A supervisor still has to confirm the person and the violation; nothing here records a name or a penalty.

Video: POST /video?required=helmet,vest&name=clip.mp4 with the file as the body starts a job (returns its id);
  GET /video/<id> gives progress and the flagged workers; POST /video/<id>/push {"location"} sends them to the supervisor;
  GET /files/<id>/<name> serves an evidence picture. GET /roles lists the trades and the equipment each one needs.

Face enrolment (supervisor sign-in required, sent as the usual Authorization header):
  GET    /faces                      who is enrolled (no photos, no templates)
  POST   /faces/enroll  {"employeeId", "image", "consent": true}
  DELETE /faces/<employeeId>
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

from ppe.annotate import crop_person, draw, draw_name
from ppe.cctv import push_items
from ppe.config import Config
from ppe.crosscheck import second_opinion
from ppe.detector import Detector
from ppe.appearance import DressBook
from ppe.faces import FaceGallery, Identity, OpenCVFaces
from ppe.identify import FrameNamer
from ppe.livefeed import LiveFeeds
from ppe.people import PersonRegistry
from ppe.pipeline import analyze
from ppe.types import ITEMS, VIOLATION, NEEDS_REVIEW
from ppe.webvideo import VideoJobs

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("DETECTOR_PORT", "5000"))
API_URL = os.environ.get("API_URL", "http://localhost:4000")
INGEST_KEY = os.environ.get("INGEST_KEY", "dev-ingest-key")
ALLOWED_ORIGINS = {"http://localhost:3001", "http://localhost:3002", "http://localhost:3003"}
MAX_BODY = 20 * 1024 * 1024
MAX_VIDEO = 400 * 1024 * 1024

weights = ROOT / "weights" / "best.pt"
extras = ROOT / "weights" / "extras.pt"
night = ROOT / "weights" / "best_night.pt"  # trained on darkened photos too; used only when a picture is dark
DETECTOR = Detector(str(weights), extra_weights=str(extras) if extras.exists() else None, night_weights=str(night) if night.exists() else None,
                    tracker=str(ROOT / "config" / "bytetrack_long.yaml") if (ROOT / "config" / "bytetrack_long.yaml").exists() else "bytetrack.yaml")

FACE_DIR = ROOT / "weights" / "faces"
try:
    FACES = OpenCVFaces(FACE_DIR / "face_detection_yunet_2023mar.onnx", FACE_DIR / "face_recognition_sface_2021dec.onnx")
except Exception as problem:  # the PPE check must keep working without the face models
    print("Face models unavailable, face matching is off:", repr(problem), file=sys.stderr)
    FACES = None
GALLERY = FaceGallery(ROOT / "data" / "faces" / "gallery.json")
REGISTRY = PersonRegistry(ROOT / "data" / "faces" / "people.json")  # dummy identities and everyone's sightings
DRESS = DressBook(ROOT / "data" / "faces" / "dress.json")  # today's clothes of each known person (cleared every day)
DUMMY_ALLOWED = os.environ.get("DUMMY_NAMES", "1") != "0"  # set DUMMY_NAMES=0 so that only enrolled employees are ever named
SETTINGS = {"dummy": DUMMY_ALLOWED}  # demo mode: unknown faces get a steady made-up name (turn off for real use)


ANALYZE_LOCK = threading.Lock()  # the detector keeps per-request state (its list of rejected objects), so one picture at a time


VIDEOS = VideoJobs(DETECTOR, ANALYZE_LOCK, ROOT / "outputs" / "web_video", API_URL, INGEST_KEY,
                   namer_factory=lambda name, location, footage: FrameNamer(FACES, GALLERY, REGISTRY, name, location, dummy_names=SETTINGS["dummy"], dress=DRESS, footage_key=footage) if FACES else None)


def _watch_frame(frame, options: dict) -> dict:
    """One check of a live-camera frame: the same analysis as an uploaded photo, sent on to the supervisor, with no made-up names (steady names need
    tracking across frames, which one-frame checks do not have). Enrolled employees are still recognised by face."""
    body = {"required": options.get("required"), "location": options.get("location", ""), "sector": options.get("sector", ""), "source": "live camera",
            "sourceName": "Phone or IP camera", "push": options.get("push", True), "dummyNames": False}
    return run(body, image=frame, raw=True)


LIVE = LiveFeeds(_watch_frame)


class Forbidden(Exception):
    pass


def decode_image(text: str):
    data = base64.b64decode(text.split(",", 1)[1] if text.startswith("data:") else text)
    return cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)


def to_data_url(image) -> str:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return "data:image/jpeg;base64," + base64.b64encode(buffer.tobytes()).decode()


def api_call(path: str, authorization: str | None = None, payload: dict | None = None, key: str | None = None):
    headers = {"content-type": "application/json"}
    if authorization:
        headers["authorization"] = authorization
    if key:
        headers["x-ingest-key"] = key
    request = urllib.request.Request(f"{API_URL}{path}", data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def require_supervisor(authorization: str | None) -> list[dict]:
    """Ask the SiteGuard API whether this sign-in belongs to a supervisor. Returns the employee list."""
    if not authorization:
        raise Forbidden("Please sign in as a supervisor.")
    try:
        return api_call("/api/employees", authorization)
    except urllib.error.HTTPError:
        raise Forbidden("Only a supervisor can manage face enrolment.")


def push_to_api(items: list[dict]) -> int:
    return push_items(API_URL, INGEST_KEY, items, detail=True)


def identities(image, result, source: str, location: str, dummy: bool, footage: str = "") -> dict[int, dict]:
    """worker_id -> who they are (an enrolled employee, or a steady dummy identity), for the workers whose face is clear."""
    if FACES is None:
        return {}
    namer = FrameNamer(FACES, GALLERY, REGISTRY, source, location, face_every=1, min_votes=1, dummy_names=dummy, dress=DRESS, footage_key=footage)
    found = dict(namer.update(image, result, None, 0))
    for verdict in result.verdicts:  # only people who broke a rule are named from their clothes
        if verdict.status == VIOLATION and verdict.worker_id not in found:
            who = namer.settle(verdict.worker_id)
            if who is not None:
                found[verdict.worker_id] = who
    return {wid: {"employeeId": w.employee_id, "name": w.name, "jobRole": w.job_role, "department": w.department, "score": w.score, "dummy": w.dummy,
                  "via": "face" if wid in namer.latest else "dress"} for wid, w in found.items()}


def run(body: dict, image=None, raw: bool = False) -> dict:
    if image is None:
        image = decode_image(str(body.get("image", "")))
    if image is None:
        raise ValueError("That is not a picture the service can read.")
    wanted = [i for i in body.get("required", ["helmet", "vest"]) if i in ITEMS] or ["helmet", "vest"]
    config = replace(Config(), required=tuple(wanted))
    with ANALYZE_LOCK:
        result = analyze(image, config, DETECTOR)
        held = set(second_opinion(image, result, DETECTOR, config))  # a second model double-checks helmet violations
    annotated = draw(image, result, prefix="Employee")  # when no face is clear, people are "Employee 1, 2, ..." and the desk lets you name them
    SETTINGS["dummy"] = DUMMY_ALLOWED and bool(body.get("dummyNames", True))
    who = identities(image, result, str(body.get("sourceName") or body.get("source") or "photo"), str(body.get("location", "")), SETTINGS["dummy"],
                     hashlib.sha1(str(body.get("image", "")).encode()).hexdigest()[:16])  # the same picture again gives the same made-up names
    note_assigned(body.get("assign"), str(body.get("sourceName") or body.get("source") or "photo"), str(body.get("location", "")))
    for key, person in (body.get("assign") or {}).items():  # the supervisor typed who this is: that beats any face match
        if str(key).isdigit() and isinstance(person, dict) and person.get("employeeId"):
            who[int(key)] = {k: person.get(k, "") for k in ("employeeId", "name", "jobRole", "department")} | {"score": 1.0, "dummy": False, "assigned": True}
    boxes = {m.worker_id: m.person.box for m in result.matches}
    for worker_id, identity in who.items():
        draw_name(annotated, boxes[worker_id], f"{identity['name']} - {identity['jobRole']}")
    workers = [
        {"id": v.worker_id, "label": (who.get(v.worker_id) or {}).get("name") or f"Employee {v.worker_id}", "crosscheck": "disagree" if v.worker_id in held else "", "status": v.status, "missing": v.missing,
         "reason": v.reason, "identity": who.get(v.worker_id)}
        for v in result.verdicts
    ]
    pushed = repeats = 0
    if body.get("push"):
        evidence = to_data_url(annotated)
        boxes_by_id = {m.worker_id: m.person.box for m in result.matches}
        flagged = [w for w in workers if w["status"] in (VIOLATION, NEEDS_REVIEW)]
        items = [
            {
                "workerRef": w["label"],
                "missing": ", ".join(w["missing"]) or "UNCLEAR",
                "reason": ("The detector was not sure. " if w["status"] == NEEDS_REVIEW else "") + w["reason"],
                "location": str(body.get("location", ""))[:80],
                "source": str(body.get("source", "feed")),
                "sourceName": str(body.get("sourceName", ""))[:120],
                "sector": str(body.get("sector", ""))[:40],
                "occurredAt": datetime.now(timezone.utc).isoformat(),
                "evidenceBase64": to_data_url(crop_person(annotated, boxes_by_id[w["id"]])) if w["id"] in boxes_by_id else evidence,  # a close-up of this worker
                "contextBase64": evidence,  # and the whole picture
                "suggested": w["identity"],
            }
            for w in flagged
        ]
        if items:
            sent = push_to_api(items)
            pushed, repeats = int(sent.get("created", 0)), int(sent.get("repeats", 0))
    out = {"annotated": "" if raw else to_data_url(annotated), "workers": workers, "pushed": pushed, "repeats": repeats, "enhanced": result.enhanced, "objects": len(result.objects)}
    if raw:
        out["_image"] = annotated
    return out


def note_assigned(assigned: dict, source: str, location: str) -> None:
    """A person named on the desk counts as seen on site, just like one recognised by face."""
    for person in (assigned or {}).values():
        if isinstance(person, dict) and person.get("employeeId"):
            REGISTRY.see(Identity(str(person["employeeId"]), str(person.get("name", "")), str(person.get("jobRole", "")), str(person.get("department", "")), 1.0), source[:60], location)


def roles_list() -> list[dict]:
    """The trades and the equipment each one must wear, read from config/ppe_rules.json (the safety officer owns that file)."""
    data = json.loads((ROOT / "config" / "ppe_rules.json").read_text(encoding="utf-8-sig"))
    return [{"key": k, "label": v.get("label", k), "required": v.get("required", []), "tools": v.get("tools", []), "alsoNeeds": v.get("also_needs", [])}
            for k, v in data.get("roles", {}).items()]


# Video speed presets: (check every Nth frame, longest side of the picture in px). Balanced is the default; Fast is for long or 4K clips.
VIDEO_SPEEDS = {"fast": (4, 1280), "balanced": (2, 1920), "thorough": (2, 3840)}


def start_video(handler, query: dict) -> dict:
    wanted = [i for i in (query.get("required", ["helmet,vest"])[0]).split(",") if i in ITEMS] or ["helmet", "vest"]
    name = (query.get("name", ["clip.mp4"])[0])[:120]
    SETTINGS["dummy"] = DUMMY_ALLOWED and query.get("dummy", ["1"])[0] != "0"
    job_id, path = VIDEOS.new_path(name)
    handler._save_raw(path)
    every, max_side = VIDEO_SPEEDS.get(query.get("speed", ["balanced"])[0], VIDEO_SPEEDS["balanced"])
    manual = query.get("every", [""])[0]
    if manual.isdigit():  # the desk's own "check every N frames" box beats the preset
        every = max(1, min(10, int(manual)))
    VIDEOS.start(job_id, path, name, wanted, query.get("location", [""])[0][:80], query.get("sector", [""])[0][:40], every=every, max_side=max_side)
    return {"id": job_id, "every": every, "maxSide": max_side}


def list_live(query: dict, authorization: str | None) -> list[dict]:
    """The cameras running for a sector, for a signed-in supervisor. A supervisor can only ask about their own sector (the head supervisor, any)."""
    try:
        allowed = {s["id"] for s in api_call("/api/sectors", authorization)}  # the API already limits this list to what the caller may see
    except urllib.error.HTTPError:
        raise Forbidden("Please sign in again.") from None
    wanted = query.get("sector", [""])[0]
    if wanted and wanted not in allowed:
        raise Forbidden("That sector is not yours.")
    return LIVE.running({wanted} if wanted else allowed)


def start_live(body: dict) -> dict:
    wanted = [i for i in body.get("required", ["helmet", "vest"]) if i in ITEMS] or ["helmet", "vest"]
    feed_id = LIVE.start(str(body.get("url", "")), {"required": wanted, "location": str(body.get("location", ""))[:80], "sector": str(body.get("sector", ""))[:40], "push": body.get("push", True) is not False, "rotate": body.get("rotate", "auto")})
    return {"id": feed_id, "url": LIVE.status(feed_id)["url"]}  # the address as it was understood, so the page can show what was really used


def enroll(body: dict, authorization: str | None) -> dict:
    employees = require_supervisor(authorization)
    if FACES is None:
        raise ValueError("The face models are not installed on this machine.")
    if body.get("consent") is not True:
        raise ValueError("Tick the consent box: the employee must know about and agree to face matching.")
    employee = next((e for e in employees if e["employeeId"] == str(body.get("employeeId", "")).upper()), None)
    if not employee:
        raise ValueError("That employee ID does not exist.")
    image = decode_image(str(body.get("image", "")))
    if image is None:
        raise ValueError("That is not a picture the service can read.")
    faces = [f for f in FACES.detect(image) if f.score >= 0.8]
    if len(faces) != 1:
        raise ValueError(f"The photo must show exactly one clear face (found {len(faces)}). Use a front-facing photo without a helmet.")
    samples = GALLERY.enroll(employee["employeeId"], employee["name"], employee.get("jobRole", ""), employee.get("department", ""), FACES.embed(image, faces[0]), True)
    return {"enrolled": employee["employeeId"], "samples": samples}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload) -> None:
        raw = json.dumps(payload).encode()
        self.send_response(code)
        self._cors()
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _cors(self) -> None:
        origin = self.headers.get("Origin", "")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Headers", "content-type, authorization")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")

    def _rotate(self, feed_id: str) -> dict:
        body = self._body() or {}
        return LIVE.rotate(feed_id, body.get("degrees"), bool(body.get("auto"))) or {"error": "No such camera."}

    def _body(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0 or length > MAX_BODY:
            raise ValueError("The picture is missing or too large.")
        return json.loads(self.rfile.read(length))

    def _save_raw(self, path: Path) -> None:
        length = int(self.headers.get("content-length", "0"))
        if length <= 0 or length > MAX_VIDEO:
            raise ValueError("The video is missing or larger than 400 MB.")
        with open(path, "wb") as out:
            left = length
            while left > 0:
                chunk = self.rfile.read(min(1 << 20, left))
                if not chunk:
                    raise ValueError("The upload stopped early.")
                out.write(chunk)
                left -= len(chunk)

    def _guard(self, work) -> None:
        try:
            self._send(200, work())
        except Forbidden as problem:
            self._send(403, {"error": str(problem)})
        except ValueError as problem:
            self._send(400, {"error": str(problem)})
        except Exception as problem:  # keep the service alive whatever one request does
            print("request failed:", repr(problem), file=sys.stderr)
            self._send(500, {"error": "The detector could not handle that request."})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        url = urllib.parse.urlparse(self.path)
        parts = url.path.strip("/").split("/")
        if url.path == "/roles":
            self._guard(roles_list)
        elif url.path == "/people":
            self._guard(lambda: (require_supervisor(self.headers.get("Authorization")), REGISTRY.reload_if_changed(), REGISTRY.people())[2])
        elif url.path == "/live":
            self._guard(lambda: list_live(urllib.parse.parse_qs(url.query), self.headers.get("Authorization")))
        elif parts[0] == "live" and len(parts) == 2:
            found = LIVE.status(parts[1])
            self._send(200, found) if found else self._send(404, {"error": "No such camera."})
        elif parts[0] == "stream" and len(parts) == 2 and parts[1].endswith(".mjpg"):
            self._stream(parts[1][:-5])
        elif parts[0] == "video" and len(parts) == 2:
            job = VIDEOS.status(parts[1])
            self._send(200, job) if job else self._send(404, {"error": "No such clip."})
        elif parts[0] == "files" and len(parts) == 3:
            found = VIDEOS.file(parts[1], parts[2])
            if not found:
                return self._send(404, {"error": "Not found."})
            raw = found.read_bytes()
            self.send_response(200)
            self._cors()
            self.send_header("content-type", "image/jpeg" if found.suffix == ".jpg" else "video/mp4")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif self.path == "/health":
            self._send(200, {"ok": True, "faces": FACES is not None, "enrolled": GALLERY.count()})
        elif self.path == "/faces":
            self._guard(lambda: (require_supervisor(self.headers.get("Authorization")), GALLERY.people())[1])
        else:
            self._send(404, {"error": "Not found."})

    def do_POST(self) -> None:
        url = urllib.parse.urlparse(self.path)
        parts = url.path.strip("/").split("/")
        if url.path == "/live":
            self._guard(lambda: start_live(self._body()))
        elif parts[0] == "live" and len(parts) == 3 and parts[2] == "stop":
            self._guard(lambda: {"stopped": LIVE.stop(parts[1])})
        elif parts[0] == "live" and len(parts) == 3 and parts[2] == "rotate":
            self._guard(lambda: self._rotate(parts[1]))
        elif url.path == "/video":
            self._guard(lambda: start_video(self, urllib.parse.parse_qs(url.query)))
        elif parts[0] == "video" and len(parts) == 3 and parts[2] == "push":
            self._guard(lambda: (lambda b: (note_assigned(b.get("assignments"), "video upload", str(b.get("location", ""))), VIDEOS.push(parts[1], str(b.get("location", "")), "video upload", b.get("assignments")))[1])(self._body()))
        elif self.path == "/analyze":
            self._guard(lambda: run(self._body()))
        elif self.path == "/faces/enroll":
            self._guard(lambda: enroll(self._body(), self.headers.get("Authorization")))
        else:
            self._send(404, {"error": "Not found."})

    def do_DELETE(self) -> None:
        if self.path == "/people/dummy":
            self._guard(lambda: (require_supervisor(self.headers.get("Authorization")), {"cleared": REGISTRY.clear_dummies()})[1])
        elif self.path.startswith("/faces/"):
            def remove():
                require_supervisor(self.headers.get("Authorization"))
                return {"removed": GALLERY.remove(self.path.rsplit("/", 1)[1].upper())}
            self._guard(remove)
        else:
            self._send(404, {"error": "Not found."})

    def _stream(self, feed_id: str) -> None:
        """The live annotated picture as a motion-JPEG stream, which a plain <img> tag can show."""
        if LIVE.status(feed_id) is None:
            return self._send(404, {"error": "No such camera."})
        self.send_response(200)
        self._cors()
        self.send_header("content-type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("cache-control", "no-store")
        self.end_headers()
        last = b""
        try:
            while True:
                jpg = LIVE.jpg(feed_id)
                state = LIVE.status(feed_id)
                if jpg and jpg is not last:
                    self.wfile.write(b"--frame\r\ncontent-type: image/jpeg\r\ncontent-length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n")
                    last = jpg
                if state is None or state["status"] in ("stopped", "error"):
                    break
                time.sleep(0.03)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            pass  # the page was closed

    def log_message(self, *args) -> None:  # quiet
        pass


if __name__ == "__main__":
    print(f"Detector service on http://localhost:{PORT}  (pushes to {API_URL}; faces {'on' if FACES else 'off'})")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
