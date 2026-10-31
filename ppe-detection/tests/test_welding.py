import numpy as np

from ppe.welding import WeldingMonitor

H, W = 360, 640
PERSON = (200, 100, 300, 340)


def frame(arc=None, sparks=True, steady_white=None):
    img = np.full((H, W, 3), 110, np.uint8)
    if steady_white:  # e.g. a white helmet: same size every frame
        x, y, r = steady_white
        img[y - r:y + r, x - r:x + r] = 255
    if arc:
        x, y, r = arc
        img[y - r:y + r, x - r:x + r] = 255
        if sparks:
            for dx, dy in [(14, -6), (-16, 4), (10, 12), (-9, -14), (20, 2), (-4, 18)]:
                img[y + dy:y + dy + 2, x + dx:x + dx + 2] = (20, 120, 255)  # orange (BGR)
    return img


def run(frames, people=(PERSON,), step=0.1):
    mon = WeldingMonitor()
    alerts = []
    for n, f in enumerate(frames):
        alerts += mon.update(n * step, f, list(people))
    return alerts


def test_a_flickering_arc_with_sparks_next_to_a_worker_is_welding():
    radii = [4, 7, 3, 8, 5, 9, 4, 7, 3, 8]
    alerts = run([frame(arc=(255 + (n % 3), 220, r)) for n, r in enumerate(radii)])
    assert alerts and alerts[0]["kind"] == "WELDING"


def test_a_steady_white_patch_such_as_a_helmet_is_not_welding():
    assert run([frame(steady_white=(250, 120, 6), sparks=False) for _ in range(10)]) == []


def test_a_flicker_with_no_sparks_is_not_welding():
    radii = [4, 7, 3, 8, 5, 9, 4, 7, 3, 8]
    assert run([frame(arc=(255, 220, r), sparks=False) for r in radii]) == []


def test_a_flicker_far_from_any_worker_is_not_welding():
    radii = [4, 7, 3, 8, 5, 9, 4, 7, 3, 8]
    assert run([frame(arc=(560, 60, r)) for r in radii]) == []


def test_one_alert_not_a_stream_of_them():
    radii = [4, 7, 3, 8, 5, 9, 4, 7, 3, 8, 5, 9]
    assert len(run([frame(arc=(255 + (n % 3), 220, r)) for n, r in enumerate(radii)])) == 1


def test_a_moving_camera_raises_no_welding_alert():
    mon = WeldingMonitor()
    alerts = []
    for n, r in enumerate([4, 7, 3, 8, 5, 9, 4, 7, 3, 8]):
        f = frame(arc=(255, 220, r))
        f[:] = np.clip(f.astype(int) + (70 if n % 2 else -40), 0, 255).astype(np.uint8)  # the whole picture brightens and darkens: camera or lighting moving
        alerts += mon.update(n * 0.1, f, [PERSON])
    assert alerts == []
