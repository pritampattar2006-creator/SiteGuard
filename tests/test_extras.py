"""Gloves, boots and goggles: matching, rules and the summary table."""
from dataclasses import replace

from ppe.associate import associate
from ppe.config import Config
from ppe.rules import evaluate
from ppe.summary import workers_table
from ppe.types import COMPLIANT, MISSING, NEEDS_REVIEW, PRESENT, UNVERIFIABLE, VIOLATION, AnalysisResult, Detection

FULL = replace(Config(), required=("helmet", "vest", "goggles", "gloves", "boots"))
SIZE = (1000, 1000)
# Worker: 100 wide, 400 tall, top at y=100 (so y=100..500). Face y~100..212, hands y~200..440, feet y~412..548.
PERSON = Detection("person", 0.9, (200, 100, 300, 500))


def det(label, box, conf=0.9):
    return Detection(label, conf, box)


def run(*dets, cfg=FULL):
    matches, unassigned = associate([PERSON, *dets], SIZE, cfg)
    return matches[0], unassigned


def test_goggles_on_the_face_are_matched():
    m, _ = run(det("goggles", (225, 120, 275, 145)))
    assert len(m.items_of("goggles")) == 1


def test_goggles_far_from_the_face_are_not():
    m, unassigned = run(det("goggles", (225, 380, 275, 405)))
    assert m.items_of("goggles") == [] and [d.label for d in unassigned] == ["goggles"]


def test_a_worker_can_own_two_gloves_and_two_boots():
    m, unassigned = run(
        det("gloves", (180, 300, 215, 335)), det("gloves", (285, 300, 320, 335)),
        det("boots", (205, 495, 245, 535)), det("boots", (255, 495, 295, 535)),
    )
    assert len(m.items_of("gloves")) == 2 and len(m.items_of("boots")) == 2 and unassigned == []


def test_gloves_lying_on_the_ground_are_not_worn():
    m, unassigned = run(det("gloves", (600, 800, 640, 830)))
    assert m.items_of("gloves") == [] and len(unassigned) == 1


def test_gloves_held_out_to_the_side_still_count():
    m, _ = run(det("gloves", (150, 280, 195, 320)))  # beyond the body edge, within the wider hand zone
    assert len(m.items_of("gloves")) == 1


def test_extras_are_ignored_when_not_required():
    m, unassigned = run(det("gloves", (180, 300, 215, 335)), cfg=Config())  # default rule: helmet + vest
    assert m.items_of("gloves") == [] and unassigned == []


def test_each_gloves_detection_goes_to_one_worker_only():
    a, b = Detection("person", 0.9, (200, 100, 300, 500)), Detection("person", 0.9, (260, 100, 360, 500))
    glove = det("gloves", (265, 300, 295, 335))
    matches, _ = associate([a, b, glove], SIZE, FULL)
    assert sum(len(m.items_of("gloves")) for m in matches) == 1


def test_full_kit_worker_is_compliant():
    m, _ = run(
        det("helmet", (225, 105, 275, 150)), det("vest", (205, 190, 295, 330)), det("goggles", (225, 125, 275, 148)),
        det("gloves", (180, 300, 215, 335)), det("boots", (205, 495, 245, 535)),
    )
    verdict = evaluate(m, FULL)
    assert verdict.status == COMPLIANT and set(verdict.states.values()) == {PRESENT}


def test_missing_extras_are_named_in_the_verdict():
    m, _ = run(det("helmet", (225, 105, 275, 150)), det("vest", (205, 190, 295, 330)))
    verdict = evaluate(m, FULL)
    assert verdict.status == VIOLATION
    assert verdict.missing == ["NO GOGGLES", "NO GLOVES", "NO BOOTS"]
    assert "No gloves found" in verdict.reason and verdict.states["gloves"] == MISSING


def test_a_small_worker_cannot_be_judged_for_gloves_or_goggles():
    small = Detection("person", 0.9, (200, 500, 240, 600))  # 100 px tall in a 1000 px photo
    matches, _ = associate([small, det("helmet", (205, 505, 235, 520)), det("vest", (203, 530, 237, 570))], SIZE, FULL)
    verdict = evaluate(matches[0], FULL)
    assert verdict.states["gloves"] == UNVERIFIABLE and verdict.states["goggles"] == UNVERIFIABLE
    assert "too small" in verdict.reason


def test_cut_off_feet_make_boots_unverifiable_but_not_gloves():
    low = Detection("person", 0.9, (200, 700, 300, 1000))
    matches, _ = associate([low, det("helmet", (225, 705, 275, 740)), det("vest", (205, 780, 295, 880))], SIZE, FULL)
    verdict = evaluate(matches[0], FULL)
    assert verdict.states["boots"] == UNVERIFIABLE and verdict.states["gloves"] == MISSING


def test_a_weak_glove_sends_the_worker_to_review_not_violation():
    cfg = replace(Config(), required=("gloves",))
    matches, _ = associate([PERSON, det("gloves", (180, 300, 215, 335), conf=0.2)], SIZE, cfg)
    verdict = evaluate(matches[0], cfg)
    assert "weak_gloves" in matches[0].flags and verdict.status == NEEDS_REVIEW


def test_table_columns_follow_the_required_items():
    m, _ = run()
    result = AnalysisResult([evaluate(m, FULL)], [m], [], False, SIZE)
    assert list(workers_table(result).columns) == ["Worker", "Helmet", "Vest", "Goggles", "Gloves", "Boots", "Status", "Missing", "Reason"]
    only_gloves = replace(Config(), required=("gloves",))
    m2, _ = run(cfg=only_gloves)
    result2 = AnalysisResult([evaluate(m2, only_gloves)], [m2], [], False, SIZE)
    assert list(workers_table(result2).columns) == ["Worker", "Gloves", "Status", "Missing", "Reason"]
