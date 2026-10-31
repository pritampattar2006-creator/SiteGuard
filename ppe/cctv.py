"""Pieces for watching a camera continuously: a face match that settles over several frames, and a sightings log."""
from __future__ import annotations

import csv
import json
import urllib.request
from collections import Counter, deque
from datetime import datetime
from pathlib import Path

from .faces import Identity


class IdentityTracker:
    """Keeps a face match steady for each tracked person.

    One frame's face match can be wrong, so a name is shown only when the same person has been matched to it in
    at least `min_votes` of the recent attempts and in `min_share` of all of them (frames where the face was seen
    but not recognised count against it).
    """

    def __init__(self, window: int = 8, min_votes: int = 2, min_share: float = 0.6):
        self.window, self.min_votes, self.min_share = window, min_votes, min_share
        self._votes: dict[int, deque] = {}
        self._known: dict[str, Identity] = {}

    def update(self, track_id: int, identity: Identity | None) -> None:
        """Record one face attempt for this person (call it only when their face was actually found)."""
        self._votes.setdefault(track_id, deque(maxlen=self.window)).append(identity.employee_id if identity else None)
        if identity:
            self._known[identity.employee_id] = identity

    def who(self, track_id: int) -> Identity | None:
        votes = self._votes.get(track_id)
        if not votes:
            return None
        names = Counter(v for v in votes if v)
        if not names:
            return None
        employee_id, count = names.most_common(1)[0]
        if count >= self.min_votes and count / len(votes) >= self.min_share:
            return self._known[employee_id]
        return None


class SightingLog:
    """A line each time an enrolled person comes into view (and again after they have been away for `gap_s` seconds)."""

    FIELDS = ["time", "employeeId", "name", "jobRole", "department", "location"]

    def __init__(self, path: Path | None, location: str = "", gap_s: float = 300.0):
        self.path, self.location, self.gap_s = Path(path) if path else None, location, gap_s
        self._last: dict[str, float] = {}
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if not self.path.exists():
                with open(self.path, "w", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow(self.FIELDS)

    def see(self, identity: Identity, now_s: float) -> bool:
        """True when this is a new arrival (and it has been logged)."""
        last = self._last.get(identity.employee_id)
        self._last[identity.employee_id] = now_s
        if last is not None and now_s - last < self.gap_s:
            return False
        if self.path:
            with open(self.path, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), identity.employee_id, identity.name,
                                        identity.job_role, identity.department, self.location])
        return True


def push_accident(api_url: str, ingest_key: str, item: dict) -> dict:
    """Send a worker-down alert to the SiteGuard API, where it becomes an accident report and sounds the supervisor's alarm."""
    request = urllib.request.Request(
        f"{api_url}/api/ingest/accidents",
        data=json.dumps(item).encode(),
        headers={"content-type": "application/json", "x-ingest-key": ingest_key},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def push_items(api_url: str, ingest_key: str, items: list[dict], detail: bool = False):
    """Send flagged workers to the SiteGuard API as 'Pending review'. Returns how many cases were created, or with detail=True
    the API's full answer (created, and repeats: people already caught today, who only get their catch count raised)."""
    request = urllib.request.Request(
        f"{api_url}/api/ingest/violations",
        data=json.dumps({"items": items}).encode(),
        headers={"content-type": "application/json", "x-ingest-key": ingest_key},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read())
    return body if detail else int(body.get("created", 0))
