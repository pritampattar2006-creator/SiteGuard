import numpy as np

from ppe.faces import FaceGallery, Identity
from ppe.identify import FrameNamer
from ppe.people import PersonRegistry, dummy_profile
from ppe.types import AnalysisResult, Detection, WorkerMatch


def vec(*parts):
    v = np.zeros(16, dtype=np.float32)
    for i, x in enumerate(parts):
        v[i] = x
    return v


def registry(tmp_path, **kw):
    return PersonRegistry(tmp_path / "people.json", **kw)


def test_the_same_face_is_always_the_same_person(tmp_path):
    r = registry(tmp_path)
    first = r.resolve(vec(1, 0.1))
    again = r.resolve(vec(0.97, 0.12))
    assert first.employee_id == again.employee_id and first.dummy


def test_different_faces_become_different_people(tmp_path):
    r = registry(tmp_path)
    a, b = r.resolve(vec(1, 0)), r.resolve(vec(0, 1))
    assert a.employee_id != b.employee_id and a.name != b.name


def test_a_look_alike_is_not_merged_and_not_invented(tmp_path):
    r = registry(tmp_path)
    r.resolve(vec(1, 0))
    assert r.resolve(vec(0.35, 0.94)) is None  # close enough to worry about, not close enough to trust


def test_a_blurry_face_never_starts_a_new_identity(tmp_path):
    r = registry(tmp_path)
    assert r.resolve(vec(1, 0), can_register=False) is None
    assert r.people() == []


def test_identities_survive_a_restart_and_can_be_cleared(tmp_path):
    first = registry(tmp_path).resolve(vec(1, 0))
    r = registry(tmp_path)
    assert r.resolve(vec(1, 0.05)).employee_id == first.employee_id
    assert r.clear_dummies() == 1
    assert registry(tmp_path).resolve(vec(1, 0)).employee_id == "E001"


def test_old_dummy_people_expire(tmp_path):
    r = registry(tmp_path, retention_days=0)
    r.resolve(vec(1, 0))
    assert registry(tmp_path, retention_days=0).resolve(vec(1, 0), can_register=False) is None


def test_dummy_profiles_are_stable_and_varied():
    assert dummy_profile(5) == dummy_profile(5)
    assert len({dummy_profile(i)["name"] for i in range(1, 25)}) == 24


def test_sightings_log_arrivals_not_every_frame(tmp_path):
    r = registry(tmp_path)
    who = r.resolve(vec(1, 0))
    assert r.see(who, "clip.mp4", "Gate 2") is True
    assert r.see(who, "clip.mp4", "Gate 2") is False
    assert r.see(who, "other.mp4", "Gate 3") is True
    assert r.people()[0]["sightingCount"] == 2


class FakeFaces:
    """Face 'embeddings' are read from a dict keyed by the person box, so no models are needed."""

    def __init__(self, table):
        self.table = table

    def detect(self, image):
        from ppe.faces import Face
        return [Face((b[0] + 10, b[1] + 5, b[0] + 70, b[1] + 70), 0.95, np.zeros(15)) for b in self.table]

    def embed(self, image, face):
        for box, v in self.table.items():
            if abs(face.box[0] - (box[0] + 10)) < 2:
                return v


def result_for(boxes, ids):
    people = [Detection("person", 0.9, b, i) for b, i in zip(boxes, ids)]
    return AnalysisResult([], [WorkerMatch(i, p, None, None) for p, i in zip(people, ids)], [], False, (800, 600))


def test_a_person_whose_track_number_changes_keeps_the_same_name(tmp_path):
    box = (100, 100, 220, 400)
    faces = FakeFaces({box: vec(1, 0.05)})
    namer = FrameNamer(faces, FaceGallery(tmp_path / "g.json"), registry(tmp_path), "clip", min_votes=2, face_every=1)
    for n in range(3):
        namer.update(None, result_for([box], [7]), None, n)
    first = namer.latest[7]
    for n in range(3, 6):  # the tracker lost him and gave him number 41
        namer.update(None, result_for([box], [41]), None, n)
    assert namer.latest[41].employee_id == first.employee_id and namer.latest[41].name == first.name


def test_enrolled_employees_are_named_before_dummies(tmp_path):
    box = (100, 100, 220, 400)
    g = FaceGallery(tmp_path / "g.json")
    g.enroll("E101", "Asha Rao", "Mason", "Masonry", vec(1, 0), True)
    namer = FrameNamer(FakeFaces({box: vec(1, 0.02)}), g, registry(tmp_path), "clip", min_votes=1, face_every=1)
    namer.update(None, result_for([box], [3]), None, 0)
    assert namer.latest[3].name == "Asha Rao" and not namer.latest[3].dummy


def test_dummy_names_can_be_switched_off(tmp_path):
    box = (100, 100, 220, 400)
    namer = FrameNamer(FakeFaces({box: vec(1, 0)}), FaceGallery(tmp_path / "g.json"), registry(tmp_path), "clip", min_votes=1, face_every=1, dummy_names=False)
    assert namer.update(None, result_for([box], [3]), None, 0) == {}
