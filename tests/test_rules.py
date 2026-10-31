from dataclasses import replace

from ppe.config import Config
from ppe.rules import evaluate, evaluate_all
from ppe.types import COMPLIANT, MISSING, NEEDS_REVIEW, PRESENT, UNVERIFIABLE, VIOLATION, Detection, WorkerMatch

CFG = Config()
PERSON = Detection("person", 0.9, (0, 100, 100, 400))
HELMET = Detection("helmet", 0.9, (25, 105, 75, 145))
VEST = Detection("vest", 0.9, (5, 170, 95, 270))


def match(helmet=None, vest=None, flags=()):
    return WorkerMatch(1, PERSON, helmet, vest, list(flags))


def test_compliant_worker():
    v = evaluate(match(HELMET, VEST), CFG)
    assert v.status == COMPLIANT and v.missing == [] and v.helmet_state == v.vest_state == PRESENT


def test_missing_helmet():
    v = evaluate(match(None, VEST), CFG)
    assert v.status == VIOLATION and v.missing == ["NO HELMET"] and v.helmet_state == MISSING


def test_missing_vest():
    v = evaluate(match(HELMET, None), CFG)
    assert v.status == VIOLATION and v.missing == ["NO VEST"]


def test_both_missing():
    v = evaluate(match(), CFG)
    assert v.missing == ["NO HELMET", "NO VEST"]


def test_vest_ignored_when_not_required():
    v = evaluate(match(HELMET, None), replace(CFG, required=("helmet",)))
    assert v.status == COMPLIANT and v.missing == []


def test_each_flag_makes_an_absent_item_unverifiable():
    for flag in ("tiny", "low_conf", "wide_box", "crowded"):
        v = evaluate(match(HELMET, None, [flag]), CFG)
        assert v.status == NEEDS_REVIEW and v.vest_state == UNVERIFIABLE, flag


def test_weak_helmet_gives_needs_review_not_violation():
    v = evaluate(match(None, VEST, ["weak_helmet"]), CFG)
    assert v.status == NEEDS_REVIEW and v.helmet_state == UNVERIFIABLE and "low confidence" in v.reason


def test_weak_helmet_does_not_hide_a_really_missing_vest():
    v = evaluate(match(None, None, ["weak_helmet"]), CFG)
    assert v.status == VIOLATION and v.missing == ["NO VEST"]


def test_edge_top_only_blocks_the_helmet():
    v = evaluate(match(None, VEST, ["edge_top"]), CFG)
    assert v.helmet_state == UNVERIFIABLE and v.status == NEEDS_REVIEW
    v = evaluate(match(HELMET, None, ["edge_top"]), CFG)
    assert v.vest_state == MISSING and v.status == VIOLATION


def test_a_bare_head_is_a_clear_missing_helmet_even_in_a_crowd():
    v = evaluate(match(None, VEST, ["crowded", "bare_head"]), CFG)
    assert v.helmet_state == MISSING and v.status == VIOLATION and v.missing == ["NO HELMET"]


def test_without_bare_head_evidence_a_crowd_still_means_review():
    v = evaluate(match(None, VEST, ["crowded"]), CFG)
    assert v.helmet_state == UNVERIFIABLE and v.status == NEEDS_REVIEW


def test_torso_cut_only_blocks_the_vest():
    v = evaluate(match(HELMET, None, ["torso_cut"]), CFG)
    assert v.vest_state == UNVERIFIABLE and v.status == NEEDS_REVIEW


def test_cut_off_feet_alone_do_not_block_the_vest():
    v = evaluate(match(HELMET, None, ["edge_bottom"]), CFG)  # legs cut off, torso fully visible
    assert v.vest_state == MISSING and v.status == VIOLATION


def test_missing_item_beats_unverifiable_item():
    v = evaluate(match(None, None, ["torso_cut"]), CFG)  # helmet really missing, vest unjudgeable
    assert v.helmet_state == MISSING and v.vest_state == UNVERIFIABLE and v.status == VIOLATION


def test_a_present_item_stays_present_even_when_flagged():
    v = evaluate(match(HELMET, VEST, ["tiny", "crowded"]), CFG)
    assert v.status == COMPLIANT


def test_reason_is_never_empty():
    for h in (None, HELMET):
        for vst in (None, VEST):
            for flags in ([], ["tiny"], ["edge_top"]):
                assert evaluate(match(h, vst, flags), CFG).reason.strip()


def test_evaluate_all_keeps_order():
    verdicts = evaluate_all([match(HELMET, VEST), match()], CFG)
    assert [v.status for v in verdicts] == [COMPLIANT, VIOLATION]
