"""Pipeline, summary, annotation and enhancement tests using a fake detector (no model needed)."""
import numpy as np

from ppe.annotate import draw, label_text
from ppe.config import Config
from ppe.enhance import apply_clahe, is_dark, maybe_enhance
from ppe.geometry import clip_box, fraction_inside, iou
from ppe.pipeline import analyze
from ppe.summary import summarize, to_csv_bytes, to_json_bytes, workers_table
from ppe.types import COMPLIANT, NEEDS_REVIEW, VIOLATION, Detection

CFG = Config()


class FakeDetector:
    def __init__(self, detections):
        self.detections = detections

    def detect(self, image, cfg):
        return self.detections


def grey(brightness=128, size=1000):
    return np.full((size, size, 3), brightness, np.uint8)


def person(x):
    return Detection("person", 0.9, (x, 100, x + 100, 400))


def test_mixed_scene_only_the_worker_with_the_helmet_is_credited():
    detections = [person(0), person(300), person(600), Detection("helmet", 0.9, (25, 105, 75, 145))]
    result = analyze(grey(), CFG, FakeDetector(detections))
    assert [v.helmet_state for v in result.verdicts] == ["PRESENT", "MISSING", "MISSING"]


def test_helmet_on_a_table_credits_nobody():
    table = Detection("helmet", 0.9, (700, 800, 750, 840))
    result = analyze(grey(), CFG, FakeDetector([person(0), table]))
    assert result.verdicts[0].helmet_state == "MISSING" and result.unassigned == [table]


def test_no_people_gives_empty_result():
    result = analyze(grey(), CFG, FakeDetector([]))
    assert result.verdicts == [] and result.matches == []


def test_dark_image_is_enhanced_in_auto_mode():
    assert analyze(grey(10), CFG, FakeDetector([])).enhanced is True
    assert analyze(grey(10), CFG, FakeDetector([]), "off").enhanced is False
    assert analyze(grey(128), CFG, FakeDetector([])).enhanced is False


def test_summary_counts_and_exports():
    detections = [person(0), person(300), Detection("helmet", 0.9, (25, 105, 75, 145)), Detection("vest", 0.9, (5, 170, 95, 270))]
    result = analyze(grey(), CFG, FakeDetector(detections))
    summary = summarize(result)
    assert (summary["total_workers"], summary["compliant"], summary["violations"]) == (2, 1, 1)
    assert summary["by_type"] == {"NO HELMET": 1, "NO VEST": 1}
    assert len(workers_table(result)) == 2
    assert to_csv_bytes(result).decode().count("\n") == 3  # header + 2 workers
    assert b'"total_workers": 2' in to_json_bytes(result)


def test_label_text_for_each_status():
    v = analyze(grey(), CFG, FakeDetector([person(0)])).verdicts[0]
    assert label_text(v) == "Worker 1: NO HELMET + NO VEST"
    v.status, v.missing = COMPLIANT, []
    assert label_text(v) == "Worker 1: OK"
    v.status = NEEDS_REVIEW
    assert label_text(v) == "Worker 1: REVIEW"
    assert VIOLATION == "VIOLATION"


def test_draw_returns_a_changed_copy():
    image = grey()
    result = analyze(image, CFG, FakeDetector([person(0)]))
    out = draw(image, result)
    assert out.shape == image.shape and not np.array_equal(out, image) and image.max() == 128


def test_a_person_lying_down_is_reported_and_not_judged_for_ppe():
    lying = Detection("person", 0.9, (100, 700, 500, 800))
    result = analyze(grey(), CFG, FakeDetector([person(0), lying]))
    assert len(result.verdicts) == 1 and result.down_candidates == [lying]
    assert len(result.people) == 2 and summarize(result)["possible_down"] == 1
    assert not np.array_equal(draw(grey(), result), draw(grey(), analyze(grey(), CFG, FakeDetector([person(0)]))))


def test_unassigned_items_are_drawn_only_when_asked():
    table_helmet = Detection("helmet", 0.9, (700, 800, 750, 840))
    image = grey()
    result = analyze(image, CFG, FakeDetector([person(0), table_helmet]))
    assert result.unassigned == [table_helmet]
    with_objects, people_only = draw(image, result, show_unassigned=True), draw(image, result, show_unassigned=False)
    assert not np.array_equal(with_objects, people_only)
    assert np.array_equal(people_only[800:840, 700:750], image[800:840, 700:750])  # nothing drawn where the helmet lies


def test_enhancement():
    dark = grey(15)
    assert is_dark(dark, CFG) and not is_dark(grey(150), CFG)
    noisy_dark = (np.random.default_rng(0).random((200, 200, 3)) * 30).astype(np.uint8)
    assert apply_clahe(noisy_dark, CFG).std() > noisy_dark.std()
    same, was = maybe_enhance(dark, CFG, "off")
    assert same is dark and was is False


def test_geometry_helpers():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0.0
    assert iou((0, 0, 10, 10), (10, 0, 20, 10)) == 0.0  # touching edges
    assert fraction_inside((2, 2, 4, 4), (0, 0, 10, 10)) == 1.0
    assert fraction_inside((0, 0, 0, 0), (0, 0, 10, 10)) == 0.0
    assert clip_box((-5, -5, 2000, 50), 1000, 800) == (0, 0, 1000, 50)
