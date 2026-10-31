from ppe.crosscheck import second_opinion
from ppe.types import MISSING, NEEDS_REVIEW, PRESENT, UNVERIFIABLE, VIOLATION, AnalysisResult, Detection, Verdict, WorkerMatch


class FakeDetector:
    def __init__(self, helmets):
        self.extra_model = object()
        self.second_label_of = {}
        self._helmets = helmets
        self.runs = 0

    def _detect_with(self, model, labels, image, cfg):
        self.runs += 1
        return self._helmets


def worker(wid, missing, box=(100, 100, 200, 400), helmet_state=MISSING):
    person = Detection("person", 0.9, box)
    verdict = Verdict(wid, VIOLATION, helmet_state, PRESENT, list(missing), "No helmet found in this worker's head zone.")
    return WorkerMatch(wid, person, None, None), verdict


def result_of(*pairs):
    return AnalysisResult([v for _, v in pairs], [m for m, _ in pairs], [], False, (640, 480))


def test_a_helmet_seen_by_the_second_model_holds_the_call_back():
    pair = worker(1, ["NO HELMET"])
    res = result_of(pair)
    held = second_opinion(None, res, FakeDetector([Detection("helmet", 0.8, (130, 90, 170, 130))]), None)
    assert held == [1]
    assert res.verdicts[0].status == NEEDS_REVIEW and res.verdicts[0].helmet_state == UNVERIFIABLE
    assert "second model" in res.verdicts[0].reason


def test_a_weak_or_misplaced_helmet_changes_nothing():
    pair = worker(1, ["NO HELMET"])
    res = result_of(pair)
    assert second_opinion(None, res, FakeDetector([Detection("helmet", 0.3, (130, 90, 170, 130)), Detection("helmet", 0.9, (130, 300, 170, 340))]), None) == []
    assert res.verdicts[0].status == VIOLATION


def test_other_violations_on_the_same_worker_stay_violations():
    pair = worker(1, ["NO HELMET", "NO VEST"])
    res = result_of(pair)
    second_opinion(None, res, FakeDetector([Detection("helmet", 0.9, (130, 90, 170, 130))]), None)
    assert res.verdicts[0].status == VIOLATION and res.verdicts[0].missing == ["NO VEST"]


def test_the_second_model_is_not_run_when_there_is_nothing_to_check():
    detector = FakeDetector([])
    res = result_of(worker(1, ["NO VEST"]))
    assert second_opinion(None, res, detector, None) == [] and detector.runs == 0
