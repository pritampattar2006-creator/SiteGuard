from ppe.config import Config
from ppe.incident import FallMonitor
from ppe.types import Detection

CFG = Config()


def standing(t_id=1, x=100):
    return Detection("person", 0.9, (x, 100, x + 100, 400), t_id)  # 100 wide, 300 tall


def lying(t_id=1, x=100):
    return Detection("person", 0.9, (x, 350, x + 300, 450), t_id)  # 300 wide, 100 tall


def run(frames):
    """frames: list of (time, [persons]). Returns every alert raised."""
    monitor, alerts = FallMonitor(CFG), []
    for t, persons in frames:
        alerts += monitor.update(t, persons)
    return alerts


def test_a_sudden_fall_that_stays_still_raises_one_fall_alert():
    frames = [(t, [standing()]) for t in (0, 0.5, 1.0)] + [(t, [lying()]) for t in (1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5)]
    alerts = run(frames)
    assert [a["kind"] for a in alerts] == ["FALL"] and alerts[0]["worker_id"] == 1


def test_a_worker_who_crouches_and_gets_back_up_raises_nothing():
    frames = [(0, [standing()]), (1, [lying()]), (2, [lying()]), (2.5, [standing()]), (3, [standing()])]
    assert run(frames) == []


def test_someone_moving_while_low_is_not_an_alert():
    frames = [(0, [standing()])] + [(1 + i * 0.5, [lying(x=100 + i * 120)]) for i in range(10)]  # crawling or working: keeps moving
    assert run(frames) == []


def test_a_person_already_lying_when_first_seen_needs_longer_stillness():
    early = run([(t, [lying()]) for t in (0, 1, 2, 3, 4)])  # 4 s: not long enough
    late = run([(t, [lying()]) for t in (0, 1, 2, 3, 4, 5, 6)])
    assert early == [] and [a["kind"] for a in late] == ["DOWN"]


def test_bending_over_for_a_long_time_is_not_lying():
    bending = Detection("person", 0.9, (100, 200, 250, 340), 1)  # aspect about 1.07: between upright and down
    assert run([(t, [bending]) for t in range(0, 12)]) == []


def test_the_alert_is_raised_once_and_rearms_after_standing_up():
    fall = [(0, [standing()])] + [(1 + i * 0.5, [lying()]) for i in range(10)]
    again = [(7, [standing()]), (7.5, [standing()])] + [(8 + i * 0.5, [lying()]) for i in range(10)]
    assert [a["kind"] for a in run(fall + again)] == ["FALL", "FALL"]


def test_two_workers_are_tracked_independently():
    frames = [(0, [standing(1, 100), standing(2, 500)]), (1, [lying(1, 100), standing(2, 500)])]
    frames += [(1 + i * 0.5, [lying(1, 100), standing(2, 500)]) for i in range(1, 9)]
    alerts = run(frames)
    assert [a["worker_id"] for a in alerts] == [1]


def test_boxes_without_a_track_id_or_with_low_confidence_are_ignored():
    untracked = Detection("person", 0.9, (100, 350, 400, 450), None)
    unsure = Detection("person", 0.3, (100, 350, 400, 450), 5)
    assert run([(t, [untracked, unsure]) for t in range(0, 12)]) == []
