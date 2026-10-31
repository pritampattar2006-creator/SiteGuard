from datetime import date

import pytest

from ppe import penalties, store

RULES = {"window_days": 30, "currency": "INR", "worker": {"propose_penalty_at": 3, "penalty_amount": 500, "escalate_to_authority_at": 5},
         "supervisor": {"escalate_to_authority_at": 2}}
TODAY = date(2026, 10, 30)


@pytest.fixture
def conn(tmp_path):
    with store.connect(tmp_path / "t.db") as c:
        yield c


def violate(conn, worker_id, day="2026-10-29", status="Open", missing="NO HELMET"):
    vid = store.add_violation(conn, worker_ref="Worker 1", missing=missing, source="photo", occurred_at=f"{day}T10:00:00", worker_id=worker_id)
    if status != "Open":
        store.set_status(conn, vid, status, "Supervisor")
    return vid


def test_two_violations_do_not_trigger_a_penalty(conn):
    w = store.add_worker(conn, "E1", "Asha")
    violate(conn, w), violate(conn, w)
    assert penalties.check_worker(conn, w, RULES, TODAY) == []


def test_the_third_violation_proposes_one_penalty_and_notifies_the_supervisor(conn):
    w = store.add_worker(conn, "E1", "Asha")
    for _ in range(3):
        violate(conn, w)
    [pid] = penalties.check_worker(conn, w, RULES, TODAY)
    p = conn.execute("SELECT * FROM penalties WHERE id = ?", (pid,)).fetchone()
    assert (p["kind"], p["status"], p["amount"], p["violation_count"]) == ("penalty", "Proposed", 500, 3)
    assert conn.execute("SELECT COUNT(*) AS n FROM violations WHERE penalty_id = ?", (pid,)).fetchone()["n"] == 3
    assert "Penalty proposed for Asha" in penalties.notifications(conn, "supervisor")[0]["message"]


def test_checking_again_never_creates_a_duplicate(conn):
    w = store.add_worker(conn, "E1", "Asha")
    for _ in range(3):
        violate(conn, w)
    penalties.check_worker(conn, w, RULES, TODAY)
    assert penalties.check_worker(conn, w, RULES, TODAY) == []
    assert len(penalties.list_for_worker(conn, w)) == 1


def test_the_next_three_violations_make_a_second_penalty(conn):
    w = store.add_worker(conn, "E1", "Asha")
    for _ in range(3):
        violate(conn, w)
    penalties.check_worker(conn, w, RULES, TODAY)
    for _ in range(3):
        violate(conn, w, day="2026-10-30")
    assert len(penalties.check_worker(conn, w, RULES, TODAY)) >= 1
    assert len([p for p in penalties.list_for_worker(conn, w) if p["kind"] == "penalty"]) == 2


def test_dismissed_and_old_violations_do_not_count(conn):
    w = store.add_worker(conn, "E1", "Asha")
    violate(conn, w, status="Dismissed"), violate(conn, w, day="2026-08-01"), violate(conn, w)
    assert penalties.check_worker(conn, w, RULES, TODAY) == []


def test_five_violations_also_escalate_a_worker_to_the_authority(conn):
    w = store.add_worker(conn, "E1", "Asha")
    for _ in range(5):
        violate(conn, w)
    penalties.check_worker(conn, w, RULES, TODAY)
    kinds = sorted(p["kind"] for p in penalties.list_for_worker(conn, w))
    assert kinds == ["escalation", "penalty"]
    assert "Escalation" in penalties.notifications(conn, "authority")[0]["message"]


def test_a_supervisor_gets_no_money_penalty_but_escalates_to_the_authority_sooner(conn):
    s = store.add_worker(conn, "S1", "Ravi", level="supervisor")
    violate(conn, s), violate(conn, s)
    [pid] = penalties.check_worker(conn, s, RULES, TODAY)
    p = conn.execute("SELECT * FROM penalties WHERE id = ?", (pid,)).fetchone()
    assert p["kind"] == "escalation" and p["amount"] == 0 and p["status"] == "Awaiting review"
    assert penalties.check_worker(conn, s, RULES, TODAY) == []  # not escalated twice


def test_authority_members_are_never_penalised(conn):
    a = store.add_worker(conn, "A1", "Head", level="authority")
    for _ in range(6):
        violate(conn, a)
    assert penalties.check_worker(conn, a, RULES, TODAY) == []


def test_nothing_is_issued_until_a_supervisor_approves_it(conn):
    w = store.add_worker(conn, "E1", "Asha")
    for _ in range(3):
        violate(conn, w)
    [pid] = penalties.check_worker(conn, w, RULES, TODAY)
    assert penalties.notifications(conn, "worker", w) == []  # the worker is told only once it is issued
    penalties.decide(conn, pid, "Issued", "Supervisor")
    assert "has been issued to you" in penalties.notifications(conn, "worker", w)[0]["message"]
    penalties.decide(conn, pid, "Disputed", "Asha")
    assert "disputed" in penalties.notifications(conn, "supervisor")[0]["message"]


def test_status_changes_are_validated(conn):
    w = store.add_worker(conn, "E1", "Asha")
    for _ in range(3):
        violate(conn, w)
    [pid] = penalties.check_worker(conn, w, RULES, TODAY)
    with pytest.raises(ValueError):
        penalties.decide(conn, pid, "Upheld", "x")  # that status belongs to escalations
    penalties.decide(conn, pid, "Waived", "Supervisor", "first offence on site")
    assert conn.execute("SELECT note FROM penalties WHERE id = ?", (pid,)).fetchone()["note"] == "first offence on site"


def test_the_shipped_rules_load():
    assert penalties.load_rules("config/penalty_rules.json")["worker"]["propose_penalty_at"] == 3


def test_an_old_register_file_is_upgraded_in_place(tmp_path):
    import sqlite3

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE workers (id INTEGER PRIMARY KEY AUTOINCREMENT, employee_id TEXT UNIQUE NOT NULL, name TEXT NOT NULL, "
                      "department TEXT NOT NULL DEFAULT '', is_demo INTEGER NOT NULL DEFAULT 0);")
    old.commit(), old.close()
    with store.connect(path) as conn:
        assert store.add_worker(conn, "E9", "Old Timer", level="supervisor")
        assert "level" in {r["name"] for r in conn.execute("PRAGMA table_info(workers)")}
