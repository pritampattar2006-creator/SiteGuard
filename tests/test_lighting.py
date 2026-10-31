import numpy as np

from ppe.lighting import apply_backlit, is_backlit
from ppe.types import MISSING, NEEDS_REVIEW, UNVERIFIABLE, VIOLATION, COMPLIANT, PRESENT, Detection, Verdict, WorkerMatch

BOX = (150, 100, 250, 400)


def scene(person_value, background_value):
    image = np.full((500, 400, 3), background_value, np.uint8)
    image[100:400, 150:250] = person_value
    return image


def worker(status=VIOLATION):
    person = Detection("person", 0.9, BOX)
    return WorkerMatch(1, person, None, None), Verdict(1, status, MISSING, MISSING, ["NO HELMET", "NO VEST"], "No helmet found.")


def test_a_dark_silhouette_on_a_bright_background_is_backlit():
    assert is_backlit(scene(25, 220), BOX)


def test_a_dark_worker_against_bright_sky_is_backlit_even_when_the_ground_around_is_dark():
    image = np.full((500, 400, 3), 40, np.uint8)  # dark ground and scaffolding all round
    image[0:100, :] = 200  # bright sky just above the worker
    image[100:400, 150:250] = 45
    assert is_backlit(image, BOX)


def test_an_ordinary_or_evenly_dark_scene_is_not_backlit():
    assert not is_backlit(scene(120, 140), BOX)  # normal daylight
    assert not is_backlit(scene(25, 30), BOX)  # a dark photo overall (night): the surroundings are not brighter
    assert not is_backlit(scene(200, 90), BOX)  # a bright person on a darker background


def test_a_backlit_violation_becomes_needs_review_and_is_ignored_by_the_video_tracker():
    match, verdict = worker()
    held = apply_backlit(scene(25, 220), [match], [verdict])
    assert held == [1] and verdict.status == NEEDS_REVIEW
    assert verdict.helmet_state == UNVERIFIABLE and verdict.vest_state == UNVERIFIABLE and verdict.missing == []
    assert "Backlit" in verdict.reason


def test_normal_lighting_and_compliant_workers_are_left_alone():
    match, verdict = worker()
    assert apply_backlit(scene(120, 140), [match], [verdict]) == [] and verdict.status == VIOLATION
    ok_match, ok = worker(COMPLIANT)
    ok.helmet_state = ok.vest_state = PRESENT
    assert apply_backlit(scene(25, 220), [ok_match], [ok]) == [] and ok.status == COMPLIANT
