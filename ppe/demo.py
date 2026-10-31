"""Demo data for presentations. Everything it creates is flagged is_demo and the names are obviously made up.

It runs the real detector on the photos in eval/test_images and files the real violations it finds against made-up demo people, then applies the
real penalty policy, so the Worker, Supervisor and Authority pages all have something to show: a proposed penalty waiting for a supervisor, and an
escalation about a supervisor waiting for the authority.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import cv2

from . import penalties, store
from .annotate import draw
from .config import Config
from .pipeline import analyze
from .service import record_violations

DEMO_PEOPLE = [  # employee id, name, department, level
    ("DEMO01", "Demo Worker A", "Masonry", "worker"),
    ("DEMO02", "Demo Worker B", "Electrical", "worker"),
    ("DEMO03", "Demo Worker C", "Scaffolding", "worker"),
    ("DEMO04", "Demo Worker D", "Civil", "worker"),
    ("DEMOSUP", "Demo Supervisor", "Site", "supervisor"),
    ("DEMOAUTH", "Demo Safety Officer", "Head office", "authority"),
]
STATUS_CYCLE = ["Open", "Acknowledged", "Open", "Resolved", "Open", "Disputed"]


def seed_demo(conn, detector, photos_dir: str | Path = "eval/test_images", cfg: Config | None = None) -> int:
    """Create the demo people (once), record the violations found in the sample photos, and apply the penalty policy. Returns how many were saved."""
    cfg = cfg or Config()
    ids = {}
    for employee_id, name, department, level in DEMO_PEOPLE:
        row = store.find_worker(conn, employee_id)
        ids[employee_id] = row["id"] if row else store.add_worker(conn, employee_id, name, department, is_demo=True, level=level)
    workers = [ids[e] for e in ("DEMO01", "DEMO02", "DEMO03", "DEMO04")]

    saved, hours_ago = [], 3
    for photo in sorted(Path(photos_dir).glob("*")):
        image = cv2.imread(str(photo))
        if image is None:
            continue
        result = analyze(image, cfg, detector)
        picks = {v.worker_id: workers[0 if len(saved) < 5 else (v.worker_id - 1) % len(workers)] for v in result.verdicts}  # worker A gets the first five
        saved += record_violations(
            conn, image_bgr=image, annotated_bgr=draw(image, result), result=result, picks=picks, source="demo", source_name=photo.name,
            occurred_at=datetime.now() - timedelta(hours=hours_ago, minutes=7 * len(saved)), location="Demo site", recorded_by="Demo supervisor", is_demo=True,
        )
        hours_ago += 4
    for vid in saved[-2:]:  # two violations by the supervisor: over their limit, so the authority has something to decide
        store.assign_worker(conn, vid, ids["DEMOSUP"], "Demo supervisor")
    for i, vid in enumerate(saved):
        status = STATUS_CYCLE[i % len(STATUS_CYCLE)]
        if status != "Open" and vid not in saved[-2:]:
            who = store.get_violation(conn, vid)["worker_name"] or "Worker"
            store.set_status(conn, vid, status, who if status in ("Acknowledged", "Disputed") else "Demo supervisor", "I was wearing it, the photo is unclear" if status == "Disputed" else "")
    for person_id in ids.values():
        penalties.check_worker(conn, person_id, today=date.today())
    return len(saved)
