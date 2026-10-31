"""Violation register: workers, violations and an event log, in one SQLite file (standard library only).

Works like a traffic e-challan system. Each saved violation gets an ID, a time, the worker it is
assigned to, evidence images, a status, and a time log of everything that happened to it.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("PPE_DB", "data/violations.db"))

# Open -> the worker acknowledges or disputes -> the supervisor resolves or dismisses.
STATUSES = ("Open", "Acknowledged", "Disputed", "Resolved", "Dismissed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS workers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT '',
    is_demo INTEGER NOT NULL DEFAULT 0,
    level TEXT NOT NULL DEFAULT 'worker'
);
CREATE TABLE IF NOT EXISTS penalties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    worker_id INTEGER NOT NULL REFERENCES workers(id),
    created_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    violation_count INTEGER NOT NULL DEFAULT 0,
    decided_by TEXT NOT NULL DEFAULT '',
    decided_at TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    to_level TEXT NOT NULL,
    worker_id INTEGER,
    message TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    video_time_s REAL,
    worker_ref TEXT NOT NULL,
    worker_id INTEGER REFERENCES workers(id),
    missing TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    evidence_path TEXT NOT NULL DEFAULT '',
    crop_path TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Open',
    recorded_by TEXT NOT NULL DEFAULT 'Supervisor',
    is_demo INTEGER NOT NULL DEFAULT 0,
    penalty_id INTEGER
);
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL,
    source_name TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    workers INTEGER NOT NULL,
    compliant INTEGER NOT NULL,
    violations INTEGER NOT NULL,
    needs_review INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    violation_id INTEGER NOT NULL REFERENCES violations(id),
    at TEXT NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
"""


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _migrate(conn) -> None:
    """Add columns that older register files do not have yet."""
    for table, column, ddl in (("workers", "level", "TEXT NOT NULL DEFAULT 'worker'"), ("violations", "penalty_id", "INTEGER")):
        if column not in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


@contextmanager
def connect(path: str | Path | None = None):
    """Open the register (creating it on first use). Commits on success, always closes."""
    path = Path(path or DEFAULT_DB)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _migrate(conn)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---- workers -------------------------------------------------------------------------------

LEVELS = ("worker", "supervisor", "authority")


def add_worker(conn, employee_id: str, name: str, department: str = "", is_demo: bool = False, level: str = "worker") -> int:
    employee_id, name = employee_id.strip(), name.strip()
    if not employee_id or not name:
        raise ValueError("Employee ID and name are both required.")
    if level not in LEVELS:
        raise ValueError(f"Level must be one of {LEVELS}.")
    try:
        cur = conn.execute(
            "INSERT INTO workers (employee_id, name, department, is_demo, level) VALUES (?, ?, ?, ?, ?)",
            (employee_id, name, department.strip(), int(is_demo), level),
        )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Employee ID {employee_id!r} already exists.") from exc
    return cur.lastrowid


def list_workers(conn) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM workers ORDER BY name").fetchall()


def find_worker(conn, employee_id: str):
    return conn.execute("SELECT * FROM workers WHERE employee_id = ?", (employee_id.strip(),)).fetchone()


# ---- violations ----------------------------------------------------------------------------

def add_violation(
    conn,
    *,
    worker_ref: str,
    missing: str,
    source: str,
    occurred_at: str | None = None,
    location: str = "",
    source_name: str = "",
    video_time_s: float | None = None,
    worker_id: int | None = None,
    reason: str = "",
    evidence_path: str = "",
    crop_path: str = "",
    recorded_by: str = "Supervisor",
    is_demo: bool = False,
) -> int:
    recorded = now()
    cur = conn.execute(
        """INSERT INTO violations (occurred_at, recorded_at, location, source, source_name, video_time_s,
               worker_ref, worker_id, missing, reason, evidence_path, crop_path, recorded_by, is_demo)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (occurred_at or recorded, recorded, location, source, source_name, video_time_s, worker_ref, worker_id,
         missing, reason, evidence_path, crop_path, recorded_by, int(is_demo)),
    )
    vid = cur.lastrowid
    add_event(conn, vid, recorded_by, "Recorded", f"{worker_ref}: {missing}")
    if worker_id is not None:
        add_event(conn, vid, recorded_by, "Assigned", _worker_name(conn, worker_id))
    return vid


def _worker_name(conn, worker_id: int) -> str:
    row = conn.execute("SELECT name, employee_id FROM workers WHERE id = ?", (worker_id,)).fetchone()
    return f"{row['name']} ({row['employee_id']})" if row else f"worker #{worker_id}"


def assign_worker(conn, violation_id: int, worker_id: int | None, actor: str) -> None:
    conn.execute("UPDATE violations SET worker_id = ? WHERE id = ?", (worker_id, violation_id))
    add_event(conn, violation_id, actor, "Assigned" if worker_id else "Unassigned", _worker_name(conn, worker_id) if worker_id else "")


def set_status(conn, violation_id: int, status: str, actor: str, note: str = "") -> None:
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}. Use one of {STATUSES}.")
    conn.execute("UPDATE violations SET status = ? WHERE id = ?", (status, violation_id))
    add_event(conn, violation_id, actor, status, note)


def add_event(conn, violation_id: int, actor: str, action: str, note: str = "") -> None:
    conn.execute(
        "INSERT INTO events (violation_id, at, actor, action, note) VALUES (?, ?, ?, ?, ?)",
        (violation_id, now(), actor, action, note),
    )


def get_violation(conn, violation_id: int):
    return conn.execute(
        """SELECT v.*, w.name AS worker_name, w.employee_id AS employee_id, w.department AS department
           FROM violations v LEFT JOIN workers w ON w.id = v.worker_id WHERE v.id = ?""",
        (violation_id,),
    ).fetchone()


def list_violations(conn, *, worker_id=None, status=None, missing=None, since=None, until=None, text=None, limit=500):
    """Newest first. `since` / `until` are ISO dates ('2026-10-30'), inclusive."""
    where, args = [], []
    if worker_id is not None:
        where.append("v.worker_id = ?"), args.append(worker_id)
    if status:
        where.append("v.status = ?"), args.append(status)
    if missing:
        where.append("v.missing LIKE ?"), args.append(f"%{missing}%")
    if since:
        where.append("date(v.occurred_at) >= date(?)"), args.append(since)
    if until:
        where.append("date(v.occurred_at) <= date(?)"), args.append(until)
    if text:
        where.append("(w.name LIKE ? OR w.employee_id LIKE ? OR v.worker_ref LIKE ? OR v.location LIKE ? OR v.source_name LIKE ?)")
        args += [f"%{text}%"] * 5
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return conn.execute(
        f"""SELECT v.*, w.name AS worker_name, w.employee_id AS employee_id, w.department AS department
            FROM violations v LEFT JOIN workers w ON w.id = v.worker_id
            {clause} ORDER BY v.occurred_at DESC, v.id DESC LIMIT ?""",
        (*args, limit),
    ).fetchall()


def log_check(conn, *, source_name: str, location: str, workers: int, compliant: int, violations: int, needs_review: int, at: str | None = None) -> None:
    """Remember that a photo or clip was checked, so a compliance rate can be worked out (not just a count of violations)."""
    conn.execute(
        "INSERT INTO checks (at, source_name, location, workers, compliant, violations, needs_review) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (at or now(), source_name, location, workers, compliant, violations, needs_review),
    )


def check_totals(conn, since: str | None = None) -> dict:
    """Workers checked, and how many were compliant, since an ISO date (all time if None)."""
    row = conn.execute(
        """SELECT COUNT(*) AS checks, COALESCE(SUM(workers), 0) AS workers, COALESCE(SUM(compliant), 0) AS compliant,
                  COALESCE(SUM(violations), 0) AS violations, COALESCE(SUM(needs_review), 0) AS needs_review
           FROM checks WHERE (? IS NULL OR date(at) >= date(?))""",
        (since, since),
    ).fetchone()
    total = row["workers"]
    return {**dict(row), "rate": round(100 * row["compliant"] / total) if total else None}


def get_events(conn, violation_id: int):
    return conn.execute("SELECT * FROM events WHERE violation_id = ? ORDER BY id", (violation_id,)).fetchall()


def stats(conn, rows=None) -> dict:
    """Counts for dashboards. Pass `rows` (from list_violations) to summarise a filtered set."""
    rows = list_violations(conn) if rows is None else rows
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    by_item: dict[str, int] = {}
    by_day: dict[str, int] = {}
    by_worker: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        for item in (m.strip() for m in r["missing"].split(",") if m.strip()):
            by_item[item] = by_item.get(item, 0) + 1
        by_day[r["occurred_at"][:10]] = by_day.get(r["occurred_at"][:10], 0) + 1
        who = r["worker_name"] or "Unassigned"
        by_worker[who] = by_worker.get(who, 0) + 1
    return {
        "total": len(rows),
        "open": by_status["Open"] + by_status["Disputed"],
        "by_status": by_status,
        "by_item": by_item,
        "by_day": dict(sorted(by_day.items())),
        "by_worker": dict(sorted(by_worker.items(), key=lambda kv: -kv[1])),
    }
