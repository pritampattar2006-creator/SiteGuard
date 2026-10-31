"""Glue between a checked photo and the violation register. No UI code, so it can be tested directly."""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import store
from .evidence import save_evidence
from .types import VIOLATION, AnalysisResult, Verdict, WorkerMatch


def violation_rows(result: AnalysisResult) -> list[tuple[Verdict, WorkerMatch]]:
    """Workers who are confirmed violations (not merely 'needs review'), with their matches."""
    return [(v, m) for v, m in zip(result.verdicts, result.matches) if v.status == VIOLATION]


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:40] or "photo"


def record_violations(
    conn,
    *,
    image_bgr,
    annotated_bgr,
    result: AnalysisResult,
    picks: dict[int, int | None],
    source: str,
    source_name: str,
    occurred_at: datetime,
    location: str = "",
    recorded_by: str = "Supervisor",
    is_demo: bool = False,
    evidence_dir: Path | None = None,
) -> list[int]:
    """Save the chosen violations. `picks` maps the worker number in the image to a roster id (or None)."""
    saved = []
    stamp = occurred_at.strftime("%Y%m%d-%H%M%S")
    for verdict, match in violation_rows(result):
        if verdict.worker_id not in picks:
            continue
        stem = f"{stamp}_{_slug(Path(source_name).stem)}_w{verdict.worker_id}"
        full, crop = save_evidence(annotated_bgr, image_bgr, match.person.box, stem, evidence_dir)
        saved.append(
            store.add_violation(
                conn,
                worker_ref=f"Worker {verdict.worker_id}",
                missing=", ".join(verdict.missing),
                source=source,
                source_name=source_name,
                occurred_at=occurred_at.isoformat(timespec="seconds"),
                location=location,
                worker_id=picks[verdict.worker_id],
                reason=verdict.reason,
                evidence_path=full,
                crop_path=crop,
                recorded_by=recorded_by,
                is_demo=is_demo,
            )
        )
    return saved


def record_video_incident(
    conn,
    *,
    incident: dict,
    evidence_file: str,
    worker_id: int | None,
    source_name: str,
    started_at: datetime,
    location: str = "",
    recorded_by: str = "Supervisor",
) -> int:
    """Save one confirmed video incident (see ppe.track.process_video) to the register."""
    from datetime import timedelta

    return store.add_violation(
        conn,
        worker_ref=f"Worker {incident['worker_id']}",
        missing=f"NO {incident['missing_item'].upper()}",
        source="video",
        source_name=source_name,
        video_time_s=incident["time_s"],
        occurred_at=(started_at + timedelta(seconds=incident["time_s"])).isoformat(timespec="seconds"),
        location=location,
        worker_id=worker_id,
        reason=f"Stayed without a {incident['missing_item']} for several consecutive frames.",
        evidence_path=evidence_file,
        recorded_by=recorded_by,
    )
