"""Video jobs for the web front end: upload a clip, follow its progress, then send the flagged workers to the supervisor.

The detector is used by one picture or clip at a time (it keeps per-request state), so a running clip holds `lock`.
"""
from __future__ import annotations

import base64
import hashlib
import re
import threading
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from .cctv import push_accident, push_items
from .hazard import HazardMonitor
from .welding import WeldingMonitor
from .config import Config
from .crosscheck import second_opinion
from .track import process_video

SAFE_NAME = re.compile(r"^[\w.\-]+$")
MAX_FRAMES = 1200  # about 80 seconds at 30 fps when every 2nd frame is checked


def _footage_key(path: Path) -> str:
    """A fingerprint of the video file (its size and first 4 MB), so the same footage uploaded again is recognised."""
    with open(path, "rb") as f:
        return hashlib.sha1(f.read(4 * 1024 * 1024) + str(path.stat().st_size).encode()).hexdigest()[:16]


ALARM_ITEMS = ("WORKER DOWN", "OBJECT NEAR WORKER", "OBJECT HIT WORKER")  # these raise an accident report and the siren
_ROOT = Path(__file__).resolve().parents[1]


def _learned_fall_monitor():
    """A fresh learned worker-down detector for one clip (its tracking state must not carry over), or None if its weights are missing.
    Measured per clip: it catches about half of falls (fewer in low light) and falsely alerts on about 7% of normal clips."""
    pose, spec = _ROOT / "weights" / "yolo11n-pose.pt", _ROOT / "weights" / "fall_model.json"
    if not (pose.exists() and spec.exists()):
        return None
    from .fall_model import FallClassifier, PoseFallMonitor
    return PoseFallMonitor(str(pose), FallClassifier.load(spec))


class VideoJobs:
    def __init__(self, detector, lock: threading.Lock, folder: Path, api_url: str, ingest_key: str, namer_factory=None):
        self.detector, self.lock, self.folder = detector, lock, Path(folder)
        self.namer_factory = namer_factory  # (source name, location, footage key) -> FrameNamer, or None for no names
        self.api_url, self.ingest_key = api_url, ingest_key
        self._jobs: dict[str, dict] = {}

    def new_path(self, filename: str) -> tuple[str, Path]:
        job_id = uuid.uuid4().hex[:12]
        suffix = Path(filename).suffix.lower()
        suffix = suffix if suffix in {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"} else ".mp4"
        (self.folder / job_id).mkdir(parents=True, exist_ok=True)
        return job_id, self.folder / job_id / f"clip{suffix}"

    def start(self, job_id: str, path: Path, name: str, required: list[str], location: str = "", sector: str = "", every: int = 2, max_side: int = 1920) -> None:
        self._jobs[job_id] = {"id": job_id, "name": name, "status": "running", "done": 0, "total": 0, "incidents": [], "error": "", "pushed": 0, "sector": sector, "every": every, "maxSide": max_side}
        threading.Thread(target=self._run, args=(job_id, path, required, location, every, max_side), daemon=True).start()

    def _progress(self, job_id: str):
        def update(done: int, total: int) -> None:
            self._jobs[job_id].update(done=done, total=total)
        return update

    def _run(self, job_id: str, path: Path, required: list[str], location: str, every: int = 2, max_side: int = 1920) -> None:
        job, folder = self._jobs[job_id], path.parent
        try:
            with self.lock:
                self.detector.reset_tracking()
                config = replace(Config(), required=tuple(required), tile_grid=0)
                namer = self.namer_factory(job["name"], location, _footage_key(path)) if self.namer_factory else None
                rows = process_video(path, config, self.detector, folder / "annotated.mp4", folder / "incidents.csv", folder / "evidence",
                                     every_nth=every, max_side=max_side, max_frames=MAX_FRAMES, progress=self._progress(job_id),
                                     on_frame=(lambda frame, result, annotated, checked: namer.update(frame, result, annotated, checked)) if namer else None,
                                     identify=(lambda worker_id: namer.settle(worker_id)) if namer else None,
                                     fall_pose=_learned_fall_monitor(), hazard=HazardMonitor(), welding=WeldingMonitor(),
                                     crosscheck=lambda frame, result: second_opinion(frame, result, self.detector, config))
                self.detector.reset_tracking()
            job["incidents"] = [{"timeS": r["time_s"], "workerId": r["worker_id"], "item": r["missing_item"], "kind": r["kind"],
                                 "detail": r["detail"], "evidence": r["evidence"], "crop": r.get("crop", ""),
                                 "person": r.get("person", ""), "personId": r.get("person_id", "")} for r in rows]
            job["status"] = "done"
        except Exception as problem:
            job.update(status="error", error=str(problem) or "The clip could not be processed.")

    def status(self, job_id: str) -> dict | None:
        return self._jobs.get(job_id)

    def file(self, job_id: str, name: str) -> Path | None:
        """An evidence picture or the annotated video of a job (the name is checked, so nothing outside the job folder is served)."""
        if job_id not in self._jobs or not SAFE_NAME.match(name):
            return None
        for candidate in (self.folder / job_id / "evidence" / name, self.folder / job_id / name):
            if candidate.is_file():
                return candidate
        return None

    def push(self, job_id: str, location: str, source_name: str, assignments: dict | None = None) -> dict:
        """Send each flagged worker (one case per worker, with their first evidence picture) to the supervisor's queue."""
        job = self._jobs.get(job_id)
        if not job or job["status"] != "done":
            raise ValueError("That clip has not finished yet.")
        by_worker: dict = {}
        accidents = [i for i in job["incidents"] if i["item"] in ALARM_ITEMS]
        for incident in (i for i in job["incidents"] if i["kind"] == "PPE"):  # one case per person: a person whose track number changed is still one person
            by_worker.setdefault(incident["personId"] or f"w{incident['workerId']}", []).append(incident)
        items = []
        for key, found in by_worker.items():
            first = found[0]
            who = {"employeeId": first["personId"], "name": first["person"]} if first["personId"] else None
            chosen = (assignments or {}).get(key)  # a name typed on the desk beats a face match
            if isinstance(chosen, dict) and chosen.get("employeeId"):
                who = {k: chosen.get(k, "") for k in ("employeeId", "name", "jobRole", "department")} | {"score": 1.0}
            picture = self.file(job_id, first["evidence"])
            close_up = self.file(job_id, first.get("crop", "")) if first.get("crop") else None
            missing = ", ".join(f"NO {i['item'].upper()}" if i["kind"] == "PPE" else str(i["item"]) for i in found)
            items.append({
                "workerRef": (who or {}).get("name") or f"Employee {first['workerId']}", "missing": ", ".join(dict.fromkeys(missing.split(", "))), "reason": first["detail"], "location": location[:80],
                "source": "video", "sector": job.get("sector", ""), "sourceName": source_name[:120], "occurredAt": datetime.now(timezone.utc).isoformat(),
                "evidenceBase64": base64.b64encode((close_up or picture).read_bytes()).decode() if (close_up or picture) else "",
                "contextBase64": base64.b64encode(picture.read_bytes()).decode() if close_up and picture else "", "suggested": who,
            })
        created = repeats = 0
        for start in range(0, len(items), 50):
            sent = push_items(self.api_url, self.ingest_key, items[start:start + 50], detail=True)
            created, repeats = created + int(sent.get("created", 0)), repeats + int(sent.get("repeats", 0))
        job["pushed"] = created
        raised = 0
        for found in accidents:  # a worker who is down is an accident alert, never an equipment violation
            picture = self.file(job_id, found["evidence"])
            who = {"employeeId": found["personId"], "name": found["person"]} if found.get("personId") else None
            try:
                push_accident(self.api_url, self.ingest_key, {
                    "kind": found["item"], "detail": found["detail"], "location": location[:80], "sector": job.get("sector", ""), "source": "video", "sourceName": source_name[:120],
                    "occurredAt": datetime.now(timezone.utc).isoformat(), "suggested": who,
                    "evidenceBase64": base64.b64encode(picture.read_bytes()).decode() if picture else ""})
                raised += 1
            except Exception:  # the alert is also shown on the desk; a down API must not hide the equipment cases
                pass
        job["accidentsRaised"] = raised
        return {"created": created, "repeats": repeats, "accidents": raised}
