import numpy as np

from ppe.hazard import HazardMonitor

H, W = 360, 640


def scene(object_box=None):
    frame = np.full((H, W, 3), 140, np.uint8)
    if object_box:
        x1, y1, x2, y2 = object_box
        frame[y1:y2, x1:x2] = 40  # a dark slab
    return frame


def run(boxes, people, step=0.2):
    mon = HazardMonitor()
    alerts = []
    for n, box in enumerate(boxes):
        alerts += mon.update(n * step, scene(box), people)
    return alerts


def dropping(x=300, start=0, stop=200, count=8, size=(110, 40)):
    ys = np.linspace(start, stop, count).astype(int)
    return [(x, y, x + size[0], y + size[1]) for y in ys]


def test_nothing_moving_raises_nothing():
    assert run([None] * 8, []) == []


def test_a_dropping_object_with_nobody_near_is_logged_without_an_alarm():
    alerts = run(dropping(), people=[(20, 150, 80, 330)])
    assert alerts and alerts[0]["kind"] == "FALLING OBJECT" and alerts[0]["alarm"] is False


def test_a_dropping_object_close_to_a_worker_raises_an_alarm():
    alerts = run(dropping(), people=[(330, 200, 400, 355)])
    assert any(a["kind"] == "OBJECT NEAR WORKER" and a["alarm"] for a in alerts)


def test_a_dropping_object_overlapping_a_worker_is_a_hit():
    alerts = run(dropping(stop=260), people=[(310, 150, 400, 330)])
    assert any(a["kind"] == "OBJECT HIT WORKER" and a["alarm"] for a in alerts)


def test_an_object_moving_sideways_or_upward_is_not_falling():
    sideways = [(60 + 50 * n, 100, 170 + 50 * n, 140) for n in range(8)]
    upward = list(reversed(dropping()))
    assert run(sideways, people=[(330, 200, 400, 355)]) == []
    assert run(upward, people=[(330, 200, 400, 355)]) == []


def test_people_moving_are_not_mistaken_for_falling_objects():
    # the "object" is inside a person's box the whole time
    alerts = run(dropping(x=100, start=0, stop=120, size=(60, 120)), people=[(80, 0, 200, 300)])
    assert alerts == []


def test_a_moving_camera_raises_no_object_alarm():
    # the whole picture changes between frames (a pan or shake), with a dark slab dropping in it too
    mon = HazardMonitor()
    alerts = []
    for n, box in enumerate(dropping()):
        f = scene(box)
        f[:] = np.clip(f.astype(int) + (60 if n % 2 else -60), 0, 255).astype(np.uint8)
        alerts += mon.update(n * 0.2, f, [(330, 200, 400, 355)])
    assert alerts == []

