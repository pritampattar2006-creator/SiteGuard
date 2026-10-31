"""Face matching, used only to SUGGEST who a flagged worker might be.

A match never records anything by itself: the supervisor still confirms the name before a violation exists.
Only a numeric face template is stored for each enrolled person (never the photo), and only after consent is recorded.
Models: OpenCV's YuNet (detector) and SFace (recogniser), both permissively licensed.
How well this works on real site footage (helmet shadows, distance, lighting) has NOT been measured.
"""
from __future__ import annotations

import json
import os

from .fileio import write_text_safely
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

Box = tuple[int, int, int, int]


@dataclass(frozen=True)
class Face:
    box: Box  # x1, y1, x2, y2
    score: float
    row: np.ndarray  # the detector's raw row; the recogniser needs it to align the face


@dataclass(frozen=True)
class Identity:
    employee_id: str
    name: str
    job_role: str
    department: str
    score: float  # cosine similarity to the closest enrolled template
    dummy: bool = False  # a made-up demo identity (see people.py), not an enrolled employee


class OpenCVFaces:
    def __init__(self, detector_path: Path, recogniser_path: Path, min_score: float = 0.7):
        import cv2

        self._detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320), min_score, 0.3, 5000)
        self._recogniser = cv2.FaceRecognizerSF.create(str(recogniser_path), "")
        self._lock = threading.Lock()  # the OpenCV objects keep state between calls

    def detect(self, image) -> list[Face]:
        height, width = image.shape[:2]
        with self._lock:
            self._detector.setInputSize((width, height))
            _, rows = self._detector.detect(image)
        faces = []
        for row in rows if rows is not None else []:
            x, y, w, h = row[:4]
            faces.append(Face((int(x), int(y), int(x + w), int(y + h)), float(row[-1]), row))
        return faces

    def embed(self, image, face: Face) -> np.ndarray:
        with self._lock:
            return self._recogniser.feature(self._recogniser.alignCrop(image, face.row)).flatten()


def _unit(vector) -> np.ndarray:
    v = np.asarray(vector, dtype=np.float32).flatten()
    return v / (np.linalg.norm(v) or 1.0)


class FaceGallery:
    """Enrolled people and their face templates, kept in one JSON file."""

    MAX_TEMPLATES = 5

    def __init__(self, path: Path, threshold: float = 0.45, margin: float = 0.05):
        self.path = Path(path)
        self.threshold = threshold  # SFace's own suggested same-person cut-off is 0.363; this is stricter on purpose
        self.margin = margin  # the best match must beat the runner-up by this much
        self._lock = threading.Lock()
        self._people: dict[str, dict] = {}
        self._mtime: float | None = None
        self.reload_if_changed()

    def _stamp(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return None

    def reload_if_changed(self) -> None:
        """Pick up enrolments made by another process (the website, or the folder tool) without a restart."""
        stamp = self._stamp()
        with self._lock:
            if stamp != self._mtime:
                self._people = json.loads(self.path.read_text(encoding="utf-8")).get("people", {}) if stamp is not None else {}
                self._mtime = stamp

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_text_safely(self.path, json.dumps({"people": self._people}))
        self._mtime = self._stamp()

    def people(self) -> list[dict]:
        with self._lock:
            return [
                {"employeeId": k, "name": v["name"], "jobRole": v["jobRole"], "department": v["department"],
                 "samples": len(v["templates"]), "enrolledAt": v["enrolledAt"]}
                for k, v in sorted(self._people.items())
            ]

    def count(self) -> int:
        return len(self._people)

    def enroll(self, employee_id: str, name: str, job_role: str, department: str, embedding, consent: bool) -> int:
        """Add one face template. Refuses unless consent was given. Returns how many templates the person now has."""
        if not consent:
            raise ValueError("Face enrolment needs the employee's consent.")
        with self._lock:
            person = self._people.setdefault(employee_id, {"templates": [], "enrolledAt": datetime.now(timezone.utc).isoformat()})
            person.update(name=name, jobRole=job_role, department=department)
            person["templates"] = (person["templates"] + [_unit(embedding).tolist()])[-self.MAX_TEMPLATES:]
            self._save()
            return len(person["templates"])

    def remove(self, employee_id: str) -> bool:
        with self._lock:
            if employee_id not in self._people:
                return False
            del self._people[employee_id]
            self._save()
            return True

    def identify(self, embedding) -> Identity | None:
        """The enrolled person this face most resembles, or None when it is not clearly any of them."""
        probe = _unit(embedding)
        with self._lock:
            scored = sorted(
                ((max(float(probe @ np.asarray(t, dtype=np.float32)) for t in p["templates"]), k) for k, p in self._people.items()),
                reverse=True,
            )
            if not scored or scored[0][0] < self.threshold:
                return None
            if len(scored) > 1 and scored[0][0] - scored[1][0] < self.margin:
                return None  # too close to call: better to say nothing than to suggest the wrong person
            score, key = scored[0]
            p = self._people[key]
            return Identity(key, p["name"], p["jobRole"], p["department"], round(score, 3))


def face_for_person(faces: list[Face], person_box: Box) -> Face | None:
    """The face that belongs to one person box: its centre sits in the upper part of the box."""
    x1, y1, x2, y2 = person_box
    limit = y1 + 0.5 * (y2 - y1)
    inside = [f for f in faces if x1 <= (f.box[0] + f.box[2]) / 2 <= x2 and y1 <= (f.box[1] + f.box[3]) / 2 <= limit]
    return max(inside, key=lambda f: f.score * (f.box[2] - f.box[0]), default=None)
