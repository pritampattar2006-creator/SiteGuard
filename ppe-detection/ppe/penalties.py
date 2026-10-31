"""Penalties and escalation: a repeat-violation policy with a human in the loop. Like a traffic challan, but nothing is issued automatically.

How it works (values come from config/penalty_rules.json, which management owns):
  * A worker's violations in the last `window_days` count towards a penalty. Every `propose_penalty_at` of them become ONE penalty,
    status Proposed. The supervisor is notified and must approve it (Issued) or waive it. The worker sees it, and may dispute it.
  * A worker at `escalate_to_authority_at` violations in the window is also escalated: a case for the authority above the supervisor.
  * A supervisor is held to the same rules for their own PPE. They get no money penalty here; at `supervisor.escalate_to_authority_at`
    violations the case goes straight to the authority.
  * A dismissed violation never counts. Re-running the check never creates duplicates.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from . import store

DEFAULT_PATH = Path("config/penalty_rules.json")
COUNTED = ("Open", "Acknowledged", "Disputed", "Resolved")  # a dismissed case was a mistake

# Penalty status: Proposed -> Issued -> Paid, or Waived / Disputed. Escalation status: Awaiting review -> Upheld / Dismissed.
PENALTY_STATUSES = ("Proposed", "Issued", "Disputed", "Paid", "Waived")
ESCALATION_STATUSES = ("Awaiting review", "Upheld", "Dismissed")


def load_rules(path: str | Path = DEFAULT_PATH) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    for key in ("window_days", "worker", "supervisor"):
        if key not in data:
            raise ValueError(f"penalty rules file is missing '{key}'")
    if data["worker"]["propose_penalty_at"] < 1:
        raise ValueError("propose_penalty_at must be at least 1")
    return data


def notify(conn, to_level: str, message: str, worker_id: int | None = None) -> None:
    conn.execute("INSERT INTO notifications (at, to_level, worker_id, message) VALUES (?, ?, ?, ?)", (store.now(), to_level, worker_id, message))


def _counted(conn, worker_id: int, since: str) -> list:
    marks = ",".join("?" * len(COUNTED))
    return conn.execute(
        f"SELECT * FROM violations WHERE worker_id = ? AND status IN ({marks}) AND date(occurred_at) >= date(?) ORDER BY occurred_at, id",
        (worker_id, *COUNTED, since),
    ).fetchall()


def check_worker(conn, worker_id: int, rules: dict | None = None, today: date | None = None) -> list[int]:
    """Apply the policy to one person. Returns the ids of penalties / escalations created now (usually none)."""
    rules = rules or load_rules()
    today = today or date.today()
    since = str(today - timedelta(days=rules["window_days"]))
    person = conn.execute("SELECT * FROM workers WHERE id = ?", (worker_id,)).fetchone()
    if person is None or person["level"] == "authority":
        return []
    in_window = _counted(conn, worker_id, since)
    created: list[int] = []

    if person["level"] == "worker":
        policy = rules["worker"]
        uncovered = [v for v in in_window if v["penalty_id"] is None]
        n = policy["propose_penalty_at"]
        while len(uncovered) >= n:
            batch, uncovered = uncovered[:n], uncovered[n:]
            reason = f"{n} violations within {rules['window_days']} days: " + "; ".join(f"#{v['id']:05d} {v['missing']}" for v in batch)
            pid = conn.execute(
                "INSERT INTO penalties (worker_id, created_at, kind, amount, currency, status, reason, violation_count) VALUES (?, ?, 'penalty', ?, ?, 'Proposed', ?, ?)",
                (worker_id, store.now(), policy["penalty_amount"], rules.get("currency", "INR"), reason, n),
            ).lastrowid
            conn.executemany("UPDATE violations SET penalty_id = ? WHERE id = ?", [(pid, v["id"]) for v in batch])
            notify(conn, "supervisor", f"Penalty proposed for {person['name']} ({person['employee_id']}): {n} violations. Please review.", worker_id)
            created.append(pid)
        threshold, subject = policy["escalate_to_authority_at"], "worker"
    else:
        threshold, subject = rules["supervisor"]["escalate_to_authority_at"], "supervisor"

    already = conn.execute("SELECT 1 FROM penalties WHERE worker_id = ? AND kind = 'escalation' AND date(created_at) >= date(?)", (worker_id, since)).fetchone()
    if len(in_window) >= threshold and not already:
        pid = conn.execute(
            "INSERT INTO penalties (worker_id, created_at, kind, amount, status, reason, violation_count) VALUES (?, ?, 'escalation', 0, 'Awaiting review', ?, ?)",
            (worker_id, store.now(), f"{subject.capitalize()} {person['name']} has {len(in_window)} violations in {rules['window_days']} days (limit {threshold}).", len(in_window)),
        ).lastrowid
        notify(conn, "authority", f"Escalation: {subject} {person['name']} ({person['employee_id']}) has {len(in_window)} violations in {rules['window_days']} days. Review needed.", worker_id)
        created.append(pid)
    return created


def decide(conn, penalty_id: int, status: str, by: str, note: str = "") -> None:
    """Approve (Issued), waive, mark paid, or dispute a penalty; or uphold / dismiss an escalation."""
    row = conn.execute("SELECT * FROM penalties WHERE id = ?", (penalty_id,)).fetchone()
    if row is None:
        raise ValueError("No such penalty.")
    allowed = PENALTY_STATUSES if row["kind"] == "penalty" else ESCALATION_STATUSES
    if status not in allowed:
        raise ValueError(f"A {row['kind']} cannot be set to {status}.")
    conn.execute("UPDATE penalties SET status = ?, decided_by = ?, decided_at = ?, note = ? WHERE id = ?", (status, by, store.now(), note, penalty_id))
    name = conn.execute("SELECT name FROM workers WHERE id = ?", (row["worker_id"],)).fetchone()["name"]
    if row["kind"] == "penalty" and status == "Issued":
        notify(conn, "worker", f"A penalty of {row['currency']} {row['amount']:.0f} has been issued to you. You can view it and dispute it.", row["worker_id"])
    elif row["kind"] == "penalty" and status == "Disputed":
        notify(conn, "supervisor", f"{name} has disputed penalty #{penalty_id}. Please review.", row["worker_id"])


def list_for_worker(conn, worker_id: int) -> list:
    return conn.execute("SELECT * FROM penalties WHERE worker_id = ? ORDER BY id DESC", (worker_id,)).fetchall()


def pending(conn, kind: str | None = None) -> list:
    where = "p.status IN ('Proposed', 'Disputed', 'Awaiting review')" + (" AND p.kind = ?" if kind else "")
    return conn.execute(
        f"SELECT p.*, w.name AS worker_name, w.employee_id, w.level FROM penalties p JOIN workers w ON w.id = p.worker_id WHERE {where} ORDER BY p.id DESC",
        (kind,) if kind else (),
    ).fetchall()


def notifications(conn, to_level: str, worker_id: int | None = None, limit: int = 30) -> list:
    if worker_id is None:
        return conn.execute("SELECT * FROM notifications WHERE to_level = ? ORDER BY id DESC LIMIT ?", (to_level, limit)).fetchall()
    return conn.execute("SELECT * FROM notifications WHERE to_level = ? AND worker_id = ? ORDER BY id DESC LIMIT ?", (to_level, worker_id, limit)).fetchall()
