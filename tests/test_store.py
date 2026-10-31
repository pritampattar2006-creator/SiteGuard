import cv2
import numpy as np
import pytest

from ppe import store
from ppe.evidence import crop_worker, save_evidence
from ppe.report import notice_pdf, summary_pdf


@pytest.fixture
def conn(tmp_path):
    with store.connect(tmp_path / "test.db") as c:
        yield c


def make_violation(conn, **overrides):
    fields = dict(worker_ref="Worker 2", missing="NO HELMET", source="photo", occurred_at="2026-10-30T10:15:00")
    fields.update(overrides)
    return store.add_violation(conn, **fields)


def test_worker_ids_must_be_unique_and_filled(conn):
    store.add_worker(conn, "E101", "Asha Rao", "Civil")
    with pytest.raises(ValueError):
        store.add_worker(conn, "E101", "Someone Else")
    with pytest.raises(ValueError):
        store.add_worker(conn, "  ", "No Id")
    assert [w["name"] for w in store.list_workers(conn)] == ["Asha Rao"]
    assert store.find_worker(conn, " E101 ")["name"] == "Asha Rao"


def test_a_new_violation_is_open_and_has_a_time_log(conn):
    vid = make_violation(conn)
    v = store.get_violation(conn, vid)
    assert v["status"] == "Open" and v["worker_name"] is None
    assert [e["action"] for e in store.get_events(conn, vid)] == ["Recorded"]


def test_assigning_a_worker_logs_the_name(conn):
    wid = store.add_worker(conn, "E7", "Ravi Kumar")
    vid = make_violation(conn, worker_id=wid)
    assert store.get_violation(conn, vid)["worker_name"] == "Ravi Kumar"
    assert "Ravi Kumar (E7)" in [e["note"] for e in store.get_events(conn, vid)]


def test_status_changes_are_logged_and_validated(conn):
    vid = make_violation(conn)
    store.set_status(conn, vid, "Disputed", "Ravi Kumar", "I was wearing it")
    store.set_status(conn, vid, "Resolved", "Supervisor", "Checked the clip")
    assert store.get_violation(conn, vid)["status"] == "Resolved"
    log = [(e["actor"], e["action"], e["note"]) for e in store.get_events(conn, vid)]
    assert log[-2:] == [("Ravi Kumar", "Disputed", "I was wearing it"), ("Supervisor", "Resolved", "Checked the clip")]
    with pytest.raises(ValueError):
        store.set_status(conn, vid, "Banana", "x")


def test_filters(conn):
    a, b = store.add_worker(conn, "E1", "Asha"), store.add_worker(conn, "E2", "Ravi")
    make_violation(conn, worker_id=a, occurred_at="2026-10-29T09:00:00")
    v2 = make_violation(conn, worker_id=b, missing="NO VEST", occurred_at="2026-10-30T09:00:00")
    store.set_status(conn, v2, "Resolved", "Supervisor")
    assert len(store.list_violations(conn)) == 2
    assert [r["worker_name"] for r in store.list_violations(conn, worker_id=a)] == ["Asha"]
    assert [r["id"] for r in store.list_violations(conn, status="Resolved")] == [v2]
    assert [r["id"] for r in store.list_violations(conn, missing="VEST")] == [v2]
    assert [r["id"] for r in store.list_violations(conn, since="2026-10-30")] == [v2]
    assert len(store.list_violations(conn, until="2026-10-29")) == 1
    assert len(store.list_violations(conn, text="ravi")) == 1


def test_newest_first(conn):
    make_violation(conn, occurred_at="2026-10-28T08:00:00")
    newest = make_violation(conn, occurred_at="2026-10-30T08:00:00")
    assert store.list_violations(conn)[0]["id"] == newest


def test_stats(conn):
    w = store.add_worker(conn, "E1", "Asha")
    make_violation(conn, worker_id=w, missing="NO HELMET, NO VEST")
    make_violation(conn, missing="NO VEST")
    s = store.stats(conn)
    assert s["total"] == 2 and s["open"] == 2
    assert s["by_item"] == {"NO HELMET": 1, "NO VEST": 2}
    assert s["by_worker"] == {"Asha": 1, "Unassigned": 1}


def test_evidence_files_are_written(tmp_path):
    image = np.full((300, 400, 3), 120, np.uint8)
    full, crop = save_evidence(image, image, (50, 40, 200, 280), "case1", tmp_path)
    assert cv2.imread(full).shape == image.shape
    assert cv2.imread(crop) is not None
    assert crop_worker(image, (0, 0, 400, 300)).shape[:2] == (300, 400)  # margin never leaves the image


def test_pdf_reports_are_valid_pdfs(conn, tmp_path):
    image = np.full((300, 400, 3), 120, np.uint8)
    full, crop = save_evidence(image, image, (50, 40, 200, 280), "case1", tmp_path)
    wid = store.add_worker(conn, "E5", "Meena Das", "Electrical")
    vid = make_violation(conn, worker_id=wid, evidence_path=full, crop_path=crop, reason="No helmet found in this worker's head zone.")
    store.set_status(conn, vid, "Acknowledged", "Meena Das")
    row = store.get_violation(conn, vid)

    notice = notice_pdf(row, store.get_events(conn, vid))
    summary = summary_pdf(store.list_violations(conn), store.stats(conn), period="30 Oct 2026")
    empty = summary_pdf([], store.stats(conn, []))
    for pdf in (notice, summary, empty):
        assert pdf.startswith(b"%PDF") and len(pdf) > 1500
    assert len(summary) > len(empty)
