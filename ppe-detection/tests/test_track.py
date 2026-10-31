import cv2
import numpy as np

from ppe.config import Config
from ppe.track import PersistenceFilter, process_video
from ppe.types import MISSING, PRESENT, UNVERIFIABLE, Detection


def feed(f, states, worker=1, item="helmet"):
    return [f.update(worker, item, s) for s in states]


def test_a_violation_lasting_one_or_two_frames_is_never_confirmed():
    f = PersistenceFilter(window=8, min_hits=5)
    assert not any(feed(f, [MISSING, MISSING, PRESENT, PRESENT, PRESENT, PRESENT]))


def test_a_steady_violation_is_confirmed_exactly_once():
    f = PersistenceFilter(window=8, min_hits=5)
    assert feed(f, [MISSING] * 12).count(True) == 1


def test_confirmation_happens_on_the_fifth_hit():
    f = PersistenceFilter(window=8, min_hits=5)
    assert feed(f, [MISSING] * 5) == [False, False, False, False, True]


def test_a_violation_that_stops_is_cleared_and_can_be_reported_again():
    f = PersistenceFilter(window=8, min_hits=5)
    first = feed(f, [MISSING] * 5)
    second = feed(f, [PRESENT] + [MISSING] * 5)
    assert first[-1] is True and second[-1] is True


def test_unverifiable_frames_are_ignored_not_counted():
    f = PersistenceFilter(window=8, min_hits=5)
    states = [MISSING, MISSING, UNVERIFIABLE, UNVERIFIABLE, MISSING, UNVERIFIABLE, MISSING, MISSING]
    assert feed(f, states)[-1] is True  # five MISSING among usable frames, the review frames skipped
    g = PersistenceFilter(window=8, min_hits=5)
    assert not any(feed(g, [MISSING, MISSING] + [UNVERIFIABLE] * 20))


def test_workers_and_items_are_tracked_independently():
    f = PersistenceFilter(window=8, min_hits=2)
    assert [f.update(1, "helmet", MISSING), f.update(2, "helmet", MISSING)] == [False, False]
    assert f.update(1, "vest", MISSING) is False
    assert f.update(1, "helmet", MISSING) is True and f.update(2, "helmet", MISSING) is True


class FakeTracker:
    """One worker, id 3, wearing a vest but never a helmet."""

    def track(self, image, cfg):
        return [Detection("person", 0.9, (100, 100, 200, 400), 3), Detection("vest", 0.9, (105, 170, 195, 270))]


def make_clip(path, frames=10):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10, (640, 480))
    for _ in range(frames):
        writer.write(np.full((480, 640, 3), 128, np.uint8))
    writer.release()


class FakeFaller:
    """One worker, wearing a helmet and vest, who stands for 1.5 s, falls, and stays on the ground."""

    def __init__(self):
        self.calls = 0

    def track(self, image, cfg):
        t = self.calls / 10
        self.calls += 1
        if t < 1.5:
            return [Detection("person", 0.9, (100, 100, 200, 400), 4), Detection("helmet", 0.9, (125, 105, 175, 145)),
                    Detection("vest", 0.9, (105, 170, 195, 270))]
        return [Detection("person", 0.9, (100, 350, 400, 450), 4)]  # lying: 300 wide, 100 tall


def test_process_video_raises_a_worker_down_alert_with_evidence(tmp_path):
    clip = tmp_path / "fall.mp4"
    make_clip(clip, frames=80)
    incidents = process_video(clip, Config(), FakeFaller(), tmp_path / "out.mp4", tmp_path / "incidents.csv", tmp_path / "evidence", every_nth=1)
    alerts = [i for i in incidents if i["kind"] in ("FALL", "DOWN")]
    assert [(a["worker_id"], a["kind"], a["missing_item"]) for a in alerts] == [(4, "FALL", "WORKER DOWN")]
    assert 4.0 <= alerts[0]["time_s"] <= 5.0  # fell at 1.5 s, still for 3 s
    assert (tmp_path / "evidence" / alerts[0]["evidence"]).exists()
    assert "WORKER DOWN" in (tmp_path / "incidents.csv").read_text()
    assert not [i for i in incidents if i["kind"] == "PPE"]  # a person on the ground is not judged for a missing helmet


def test_process_video_writes_one_incident_with_evidence(tmp_path):
    clip = tmp_path / "clip.mp4"
    make_clip(clip)
    incidents = process_video(clip, Config(), FakeTracker(), tmp_path / "out.mp4", tmp_path / "incidents.csv", tmp_path / "evidence", every_nth=1)
    assert [(i["worker_id"], i["missing_item"]) for i in incidents] == [(3, "helmet")]
    assert (tmp_path / "out.mp4").stat().st_size > 0
    files = sorted(p.name for p in (tmp_path / "evidence").glob("*.jpg"))
    assert len(files) == 2 and files[0].endswith("_crop.jpg") is False and files[1].endswith("_crop.jpg")  # the whole picture and a close-up of the worker
    assert incidents[0]["crop"] == files[1]
    assert (tmp_path / "incidents.csv").read_text().count("\n") == 2  # header + one row
