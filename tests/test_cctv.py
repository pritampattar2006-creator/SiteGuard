from ppe.cctv import IdentityTracker, SightingLog
from ppe.faces import Identity


def person(eid, score=0.6):
    return Identity(eid, f"Name {eid}", "Mason", "Civil", score)


def test_one_lucky_frame_is_not_enough():
    t = IdentityTracker()
    t.update(1, person("E1"))
    assert t.who(1) is None


def test_name_appears_once_the_match_repeats():
    t = IdentityTracker()
    for _ in range(3):
        t.update(1, person("E1"))
    assert t.who(1).employee_id == "E1"


def test_unrecognised_frames_count_against_the_name():
    t = IdentityTracker()
    t.update(1, person("E1"))
    t.update(1, person("E1"))
    for _ in range(4):
        t.update(1, None)
    assert t.who(1) is None  # 2 of 6 is not a steady match


def test_people_with_different_matches_do_not_mix():
    t = IdentityTracker()
    for _ in range(3):
        t.update(1, person("E1"))
        t.update(2, person("E2"))
    assert (t.who(1).employee_id, t.who(2).employee_id) == ("E1", "E2")
    assert t.who(3) is None


def test_a_flip_flopping_track_is_not_named():
    t = IdentityTracker()
    for who in ["E1", "E2", "E1", "E2", "E1", "E2"]:
        t.update(1, person(who))
    assert t.who(1) is None


def test_sightings_are_logged_on_arrival_and_after_a_gap(tmp_path):
    log = SightingLog(tmp_path / "s.csv", location="Gate 2", gap_s=300)
    assert log.see(person("E1"), 0) is True
    assert log.see(person("E1"), 100) is False
    assert log.see(person("E1"), 200) is False  # still in view: the gap is measured from the last time they were seen
    assert log.see(person("E1"), 600) is True
    rows = (tmp_path / "s.csv").read_text().strip().splitlines()
    assert len(rows) == 3 and "Gate 2" in rows[1]
