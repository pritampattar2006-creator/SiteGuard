from eval.run_eval import Truth, by_group, compare, load_ground_truth, to_markdown
from ppe.types import COMPLIANT, VIOLATION, AnalysisResult, Detection, Verdict


def verdict(i, status, missing=()):
    return Verdict(i, status, "PRESENT", "PRESENT", [f"NO {m.upper()}" for m in missing], "because")


def result(verdicts, unassigned=()):
    return AnalysisResult(verdicts, [], list(unassigned), False, (100, 100))


def test_correct_workers_score_correct():
    truth = Truth("mixed", [(COMPLIANT, frozenset()), (VIOLATION, frozenset({"helmet"}))])
    rows, problems = compare("a.jpg", truth, result([verdict(1, COMPLIANT), verdict(2, VIOLATION, ["helmet"])]))
    assert [r.correct for r in rows] == [True, True] and problems == []


def test_wrong_missing_item_is_wrong():
    truth = Truth("mixed", [(VIOLATION, frozenset({"helmet"}))])
    rows, _ = compare("a.jpg", truth, result([verdict(1, VIOLATION, ["vest"])]))
    assert rows[0].correct is False


def test_worker_count_mismatch_fails_the_whole_image():
    truth = Truth("crowded", [(COMPLIANT, frozenset()), (COMPLIANT, frozenset())])
    rows, problems = compare("a.jpg", truth, result([verdict(1, COMPLIANT)]))
    assert not any(r.correct for r in rows) and "expected 2 workers, detected 1" in problems[0]


def test_unassigned_helmet_check():
    truth = Truth("helmet_on_table", [(VIOLATION, frozenset({"helmet"}))], unassigned_helmets=1)
    table_helmet = Detection("helmet", 0.9, (0, 0, 5, 5))
    _, ok = compare("a.jpg", truth, result([verdict(1, VIOLATION, ["helmet"])], [table_helmet]))
    _, bad = compare("a.jpg", truth, result([verdict(1, VIOLATION, ["helmet"])]))
    assert ok == [] and "unassigned helmet" in bad[0]


def test_group_table_and_markdown():
    truth = Truth("easy", [(COMPLIANT, frozenset())])
    rows, _ = compare("a.jpg", truth, result([verdict(1, COMPLIANT)]))
    table = by_group(rows)
    assert table[0]["accuracy"] == "100%"
    assert "| easy | 1 | 1 | 1 | 100% |" in to_markdown(table)


def test_load_ground_truth(tmp_path):
    path = tmp_path / "gt.csv"
    path.write_text(
        "image,group,worker,expected_status,expected_missing,expected_unassigned_helmets\n"
        "m.jpg,mixed,1,COMPLIANT,,0\n"
        "m.jpg,mixed,2,VIOLATION,helmet;vest,0\n"
    )
    truth = load_ground_truth(path)["m.jpg"]
    assert truth.workers == [("COMPLIANT", frozenset()), ("VIOLATION", frozenset({"helmet", "vest"}))]
    assert truth.unassigned_helmets == 0
