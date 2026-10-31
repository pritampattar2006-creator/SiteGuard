import numpy as np
import pytest

from ppe.faces import Face, FaceGallery, face_for_person


def vec(*parts):
    v = np.zeros(8, dtype=np.float32)
    for i, x in enumerate(parts):
        v[i] = x
    return v


@pytest.fixture
def gallery(tmp_path):
    return FaceGallery(tmp_path / "g.json", threshold=0.45, margin=0.05)


def enrol(g, eid, v, consent=True):
    return g.enroll(eid, f"Name {eid}", "Mason", "Civil", v, consent)


def test_enrolment_needs_consent(gallery):
    with pytest.raises(ValueError):
        enrol(gallery, "E1", vec(1), consent=False)
    assert gallery.count() == 0


def test_finds_the_right_person(gallery):
    enrol(gallery, "E1", vec(1, 0))
    enrol(gallery, "E2", vec(0, 1))
    who = gallery.identify(vec(0.95, 0.1))
    assert who and who.employee_id == "E1" and who.job_role == "Mason"


def test_stranger_is_not_matched(gallery):
    enrol(gallery, "E1", vec(1, 0))
    assert gallery.identify(vec(0, 0, 1)) is None


def test_too_close_to_call_gives_no_name(gallery):
    enrol(gallery, "E1", vec(1, 0.1))
    enrol(gallery, "E2", vec(1, 0.12))
    assert gallery.identify(vec(1, 0.11)) is None


def test_templates_are_capped_and_survive_a_restart(gallery, tmp_path):
    for i in range(8):
        enrol(gallery, "E1", vec(1, i * 0.01))
    assert gallery.people()[0]["samples"] == FaceGallery.MAX_TEMPLATES
    again = FaceGallery(tmp_path / "g.json")
    assert again.identify(vec(1, 0)).employee_id == "E1"


def test_only_templates_are_stored_and_removal_works(gallery, tmp_path):
    enrol(gallery, "E1", vec(1))
    text = (tmp_path / "g.json").read_text()
    assert "templates" in text and "image" not in text
    assert gallery.remove("E1") and not gallery.remove("E1")
    assert gallery.identify(vec(1)) is None


def face(cx, cy, size=20, score=0.9):
    return Face((cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2), score, np.zeros(15))


def test_face_goes_to_the_person_whose_head_it_is_in():
    person = (100, 100, 200, 400)
    assert face_for_person([face(150, 140)], person) is not None
    assert face_for_person([face(150, 350)], person) is None  # a face in the legs area is someone else's
    assert face_for_person([face(500, 140)], person) is None  # outside the box


def test_gallery_picks_up_another_process_enrolling_someone(tmp_path):
    a = FaceGallery(tmp_path / "g.json")
    b = FaceGallery(tmp_path / "g.json")
    assert a.count() == 0
    enrol(b, "E1", vec(1))
    a.reload_if_changed()
    assert a.identify(vec(1)).employee_id == "E1"
    b.remove("E1")
    a.reload_if_changed()
    assert a.count() == 0
