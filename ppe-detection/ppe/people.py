"""People seen on camera who are not enrolled employees, given a steady dummy identity so the same face is the same person.

DEMO MODE: the names, roles and IDs here are made up. They do not belong to anyone, and nothing links them to a real
employee. A face template is stored for each dummy person (never the photo) so the same face is recognised in the next
photo, video or camera. Templates expire after `retention_days` without a sighting, and the supervisor can clear them all.

Merging two different people into one is worse than splitting one person into two, so matching here is strict.
"""
from __future__ import annotations

import json
import os

from .fileio import write_text_safely
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from .faces import Identity, _unit

FIRST = ["Aarav", "Vihaan", "Arjun", "Rohan", "Kiran", "Suresh", "Manoj", "Deepak", "Anil", "Ramesh", "Sanjay", "Mahesh",
         "Prakash", "Nitin", "Ganesh", "Ajay", "Vikram", "Raju", "Santosh", "Mohan", "Imran", "Farhan", "Joseph", "Basavaraj"]
LAST = ["Naik", "Patil", "Desai", "Kulkarni", "Shetty", "Gowda", "Pawar", "Jadhav", "Kamble", "Hegde", "Rathod", "Bhat",
        "Mane", "Joshi", "Shinde", "Khan", "D'Souza", "Madar", "Gaonkar", "Chavan"]
TRADES = ["Mason", "Electrician", "Carpenter", "Welder", "Scaffolder", "Helper", "Painter", "Plumber", "Crane operator", "Bar bender"]
DEPARTMENTS = ["Civil", "Electrical", "Structure", "Finishing", "Plumbing", "Scaffolding", "Rigging"]


def dummy_profile(number: int) -> dict:
    """The made-up name, role and department for the nth dummy person (always the same for the same number)."""
    return {
        "employeeId": f"E{number:03d}",
        "name": f"{FIRST[number % len(FIRST)]} {LAST[(number * 7 + 3) % len(LAST)]}",
        "jobRole": TRADES[(number * 3) % len(TRADES)],
        "department": DEPARTMENTS[(number * 5) % len(DEPARTMENTS)],
    }


ROSTER_SIZE = 120  # config/dummy_roster.json lists this many made-up employees


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PersonRegistry:
    MAX_TEMPLATES = 8

    def __init__(self, path: Path, threshold: float = 0.4, margin: float = 0.06, retention_days: int = 7, gap_s: float = 300.0):
        self.path = Path(path)
        self.threshold, self.margin, self.retention_days, self.gap_s = threshold, margin, retention_days, gap_s
        self._lock = threading.Lock()
        self._people: dict[str, dict] = {}
        self._next = 1
        self._keys: dict[str, str] = {}  # footage key -> the made-up identity given to that person in that footage
        self._mtime: float | None = None
        self.reload_if_changed()

    # ---- storage ----------------------------------------------------------------------------------
    def _stamp(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except FileNotFoundError:
            return None

    def reload_if_changed(self) -> None:
        stamp = self._stamp()
        with self._lock:
            if stamp == self._mtime:
                return
            data = json.loads(self.path.read_text(encoding="utf-8")) if stamp is not None else {}
            self._people, self._next, self._mtime = data.get("people", {}), data.get("next", 1), stamp
            self._keys = data.get("keys", {})
            self._expire()

    def _expire(self) -> None:
        cutoff = (_now() - timedelta(days=self.retention_days)).isoformat()
        for key in [k for k, p in self._people.items() if p.get("dummy") and p["lastSeen"] < cutoff]:
            del self._people[key]

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_text_safely(self.path, json.dumps({"people": self._people, "next": self._next, "keys": self._keys}))
        self._mtime = self._stamp()

    # ---- recognising and registering --------------------------------------------------------------
    def _best(self, probe) -> tuple[str | None, float, float]:
        """(closest dummy person, its score, the runner-up's score)."""
        scored = sorted(
            ((max(float(probe @ np.asarray(t, dtype=np.float32)) for t in p["templates"]), k)
             for k, p in self._people.items() if p.get("dummy") and p["templates"]), reverse=True)
        if not scored:
            return None, 0.0, 0.0
        return scored[0][1], scored[0][0], scored[1][0] if len(scored) > 1 else 0.0

    def _identity(self, key: str, score: float) -> Identity:
        p = self._people[key]
        return Identity(key, p["name"], p["jobRole"], p["department"], round(score, 3), True)

    def resolve(self, embedding, can_register: bool = True) -> Identity | None:
        """The dummy person this face belongs to: an existing one if it clearly matches, else (when allowed) a new one."""
        probe = _unit(embedding)
        with self._lock:
            key, score, runner = self._best(probe)
            if key is not None and score >= self.threshold and score - runner >= self.margin:
                p = self._people[key]
                if score < 0.8 and len(p["templates"]) < self.MAX_TEMPLATES:  # a different angle or light: keep it for next time
                    p["templates"].append(probe.tolist())
                p["lastSeen"] = _now().isoformat()
                self._save()
                return self._identity(key, score)
            if key is not None and score >= self.threshold - 0.1:
                return None  # too close to call (or close to someone): say nothing, and do not create a look-alike
            if not can_register:
                return None
            number = self._next
            self._next += 1
            profile = dummy_profile(number)
            now = _now().isoformat()
            self._people[profile["employeeId"]] = {**profile, "dummy": True, "templates": [probe.tolist()], "firstSeen": now, "lastSeen": now, "sightings": []}
            self._save()
            return self._identity(profile["employeeId"], 1.0)

    def identity_for_key(self, key: str) -> Identity | None:
        """The made-up identity for one person in one piece of footage: the same footage always gives the same one."""
        with self._lock:
            held = self._keys.get(key)
            if held and held in self._people:
                return self._identity(held, 1.0)
        who = self.new_unseen()
        if who is not None:
            with self._lock:
                self._keys[key] = who.employee_id
                self._save()
        return who

    def new_unseen(self) -> Identity | None:
        """A new dummy person for someone whose face was never seen (named by their clothes only). None once the roster is used up."""
        with self._lock:
            number = self._next
            if number > ROSTER_SIZE:
                return None
            self._next += 1
            profile = dummy_profile(number)
            now = _now().isoformat()
            self._people[profile["employeeId"]] = {**profile, "dummy": True, "templates": [], "firstSeen": now, "lastSeen": now, "sightings": []}
            self._save()
            return self._identity(profile["employeeId"], 1.0)

    # ---- sightings (dummy people and enrolled employees alike) --------------------------------------
    def see(self, identity: Identity, source: str, location: str) -> bool:
        """Log a sighting; returns True when it is new (not just the same person still in view)."""
        now = _now()
        with self._lock:
            entry = self._people.setdefault(identity.employee_id, {
                "employeeId": identity.employee_id, "name": identity.name, "jobRole": identity.job_role, "department": identity.department,
                "dummy": identity.dummy, "templates": [], "firstSeen": now.isoformat(), "lastSeen": now.isoformat(), "sightings": []})
            last = entry["sightings"][-1] if entry["sightings"] else None
            fresh = last is None or (now - datetime.fromisoformat(last["at"])).total_seconds() >= self.gap_s or last["source"] != source
            entry["lastSeen"] = now.isoformat()
            if fresh:
                entry["sightings"] = (entry["sightings"] + [{"at": now.isoformat(), "source": source[:60], "location": location[:80]}])[-50:]
            self._save()
            return fresh

    def people(self) -> list[dict]:
        with self._lock:
            return sorted(
                ({"employeeId": k, "name": p["name"], "jobRole": p["jobRole"], "department": p["department"], "dummy": bool(p.get("dummy")),
                  "firstSeen": p["firstSeen"], "lastSeen": p["lastSeen"], "sightings": p["sightings"][-20:], "sightingCount": len(p["sightings"])}
                 for k, p in self._people.items() if p["sightings"]),
                key=lambda p: p["lastSeen"], reverse=True)

    def clear_dummies(self) -> int:
        with self._lock:
            gone = [k for k, p in self._people.items() if p.get("dummy")]
            for k in gone:
                del self._people[k]
            self._keys = {}
            self._next = 1
            self._save()
            return len(gone)
