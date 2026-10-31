from datetime import date

from ppe import insights, store

TODAY = date(2026, 10, 30)


def rec(day, status="Open", missing="NO HELMET", worker="Asha", hour=10, location="Gate 2"):
    return {"occurred_at": f"{day}T{hour:02d}:15:00", "status": status, "missing": missing, "worker_name": worker, "location": location}


def test_a_worker_with_no_violations_scores_100():
    assert insights.safety_score([], TODAY) == 100


def test_each_recent_violation_costs_points_and_unanswered_ones_cost_more():
    assert insights.safety_score([rec("2026-10-29", "Resolved")], TODAY) == 92
    assert insights.safety_score([rec("2026-10-29", "Open")], TODAY) == 88


def test_old_and_dismissed_violations_do_not_count():
    assert insights.safety_score([rec("2026-08-01"), rec("2026-10-29", "Dismissed")], TODAY) == 100


def test_score_never_goes_below_zero():
    assert insights.safety_score([rec("2026-10-29")] * 12, TODAY) == 0


def test_score_labels():
    assert [insights.score_label(s)[0] for s in (100, 80, 60, 10)] == ["Excellent", "Good", "Needs attention", "At risk"]


def test_days_since_last_and_badges():
    assert insights.days_since_last([], TODAY) is None
    assert insights.days_since_last([rec("2026-10-20")], TODAY) == 10
    assert [b[0] for b in insights.badges([], TODAY)] == ["Clean record"]
    assert "7 days clean" in [b[0] for b in insights.badges([rec("2026-10-20", "Resolved")], TODAY)]
    assert "30 days clean" in [b[0] for b in insights.badges([rec("2026-09-01", "Resolved")], TODAY)]
    assert insights.badges([rec("2026-10-29", "Open")], TODAY) == []


def test_calendar_has_the_requested_weeks_and_counts_each_day():
    calendar = insights.activity_calendar([rec("2026-10-29"), rec("2026-10-29", "Resolved")], weeks=4, today=TODAY)
    assert len(calendar) == 4 and all(len(week) == 7 for week in calendar)
    counts = {d: n for week in calendar for d, n in week}
    assert counts[date(2026, 10, 29)] == 2 and counts[date(2026, 10, 28)] == 0
    assert calendar[0][0][0].weekday() == 0


def test_daily_series_is_oldest_first():
    assert insights.daily_series([rec("2026-10-30"), rec("2026-10-28")], days=3, today=TODAY) == [1, 0, 1]


def test_hour_and_weekday_counts():
    rows = [rec("2026-10-30", hour=9), rec("2026-10-30", hour=9), rec("2026-10-29", hour=14)]
    assert insights.hourly_counts(rows)[9] == 2 and insights.hourly_counts(rows)[14] == 1
    assert (4, 9, 2) in insights.weekday_hour(rows)  # 30 Oct 2026 is a Friday (weekday 4)
    assert sum(n for _, _, n in insights.weekday_hour(rows)) == 3


def test_repeat_offenders_and_risk():
    rows = [rec("2026-10-29", worker="Asha"), rec("2026-10-28", worker="Asha"), rec("2026-10-28", worker="Ravi")]
    assert insights.repeat_offenders(rows) == [("Asha", 2)]
    assert insights.risk_level(3, 0)[0] == "High" and insights.risk_level(1, 1)[0] == "Watch" and insights.risk_level(1, 0)[0] == "Low"


def test_sentences_describe_the_data():
    rows = [rec("2026-10-29", hour=10), rec("2026-10-28", hour=10, missing="NO VEST", worker="Ravi")]
    text = " ".join(insights.sentences(rows))
    assert "10:00" in text and "Gate 2" in text
    assert insights.sentences([]) == ["No violations recorded yet, so there is nothing to analyse."]


def test_tips_match_the_violation():
    assert len(insights.tips_for(["NO HELMET", "NO HELMET", "NO BOOTS"])) == 2
    assert insights.tips_for(["something else"]) == []


def test_compliance_rate_comes_from_logged_checks(tmp_path):
    with store.connect(tmp_path / "t.db") as conn:
        assert store.check_totals(conn)["rate"] is None
        store.log_check(conn, source_name="a.jpg", location="Gate", workers=4, compliant=3, violations=1, needs_review=0, at="2026-10-30T09:00:00")
        store.log_check(conn, source_name="b.jpg", location="Gate", workers=6, compliant=2, violations=3, needs_review=1, at="2026-10-01T09:00:00")
        assert store.check_totals(conn)["rate"] == 50  # 5 of 10
        assert store.check_totals(conn, since="2026-10-15")["rate"] == 75
