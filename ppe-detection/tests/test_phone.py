import numpy as np

from ppe.phone import CALL, PHONE_IN_HAND, POSSIBLE_CALL, PhoneMonitor, phone_use

PERSON = (100, 60, 300, 400)
# a standing person, head 40 px wide, arms hanging
BASE = {3: (180, 100), 4: (220, 100), 1: (190, 92), 2: (210, 92), 0: (200, 100), 5: (150, 160), 6: (250, 160),
        7: (140, 230), 8: (260, 230), 9: (140, 300), 10: (260, 300)}


def pose(**moves):
    """Pose points and confidences for BASE with some joints moved: pose(L_WRI=(x, y))."""
    names = {"L_WRI": 9, "R_WRI": 10, "L_ELB": 7, "R_ELB": 8}
    pts = dict(BASE)
    for name, xy in moves.items():
        pts[names[name]] = xy
    kp = np.zeros((17, 2), float)
    kc = np.zeros(17, float)
    for i, xy in pts.items():
        kp[i], kc[i] = xy, 0.9
    return kp, kc


def box_at(x, y, half=10):
    return (x - half, y - half, x + half, y + half)


def test_phone_at_the_raised_hand_is_a_call():
    kp, kc = pose(L_WRI=(175, 110), L_ELB=(150, 200))
    result = phone_use(PERSON, kp, kc, [box_at(172, 108)])
    assert result["kind"] == CALL and not result["needs_review"]


def test_phone_in_a_lowered_hand_is_only_in_hand():
    kp, kc = pose()
    assert phone_use(PERSON, kp, kc, [box_at(140, 300)])["kind"] == PHONE_IN_HAND


def test_raised_hand_without_a_phone_is_only_a_guess_for_review():
    kp, kc = pose(L_WRI=(175, 110), L_ELB=(150, 200))
    result = phone_use(PERSON, kp, kc, [])
    assert result["kind"] == POSSIBLE_CALL and result["needs_review"]


def test_arms_down_and_no_phone_reports_nothing():
    kp, kc = pose()
    assert phone_use(PERSON, kp, kc, []) is None


def test_a_phone_lying_far_from_both_hands_is_not_phone_use():
    kp, kc = pose()
    assert phone_use(PERSON, kp, kc, [box_at(20, 380)]) is None


def test_waving_a_hand_high_and_away_from_the_head_is_not_a_call():
    kp, kc = pose(L_WRI=(110, 40), L_ELB=(120, 110))
    assert phone_use(PERSON, kp, kc, []) is None


def test_a_hand_not_raised_above_the_shoulder_is_not_at_the_head():
    kp, kc = pose(L_WRI=(175, 170), L_ELB=(150, 200))  # level with the ear horizontally, but below the shoulder line
    assert phone_use(PERSON, kp, kc, []) is None


def test_a_small_far_person_is_not_judged():
    kp, kc = pose(L_WRI=(175, 110), L_ELB=(150, 200))
    assert phone_use((100, 60, 140, 120), kp, kc, [box_at(172, 108)]) is None


def test_a_wrist_the_pose_model_is_unsure_about_is_ignored():
    kp, kc = pose()
    kc[9] = 0.1  # the left wrist is too uncertain, so a phone beside it is not credited to it
    assert phone_use(PERSON, kp, kc, [box_at(140, 300)]) is None


def test_the_other_hand_works_the_same():
    kp, kc = pose(R_WRI=(225, 110), R_ELB=(250, 200))
    assert phone_use(PERSON, kp, kc, [box_at(228, 108)])["kind"] == CALL


class FakeMonitor(PhoneMonitor):
    """The video logic without any model: the frames are replaced by scripted findings."""

    def __init__(self, script):
        self.window, self.need, self.release, self.cooldown, self.smooth = 5, 3, 1, 20.0, 0.5
        self._hist, self._alerted, self._on, self._last, self._script = {}, {}, set(), {}, iter(script)

    def look(self, frame_bgr, track=False):
        return next(self._script)


CALLING = {"kind": CALL, "reason": "call", "needs_review": False, "box": PERSON, "worker_id": 7, "phones": []}


def run(script, step=0.5):
    mon = FakeMonitor(script)
    alerts = []
    for n in range(len(script)):
        alerts += mon.update(n * step, None)
    return alerts


def test_one_frame_of_phone_use_raises_nothing():
    assert run([[CALLING]] + [[]] * 8) == []


def test_phone_use_that_keeps_going_raises_one_alert_for_that_person():
    alerts = run([[CALLING]] * 10)
    assert len(alerts) == 1 and alerts[0]["worker_id"] == 7 and alerts[0]["kind"] == "PHONE_CALL"


def test_a_guess_that_keeps_going_is_flagged_for_review():
    guess = {**CALLING, "kind": POSSIBLE_CALL, "needs_review": True}
    alerts = run([[guess]] * 6)
    assert alerts and alerts[0]["needs_review"]


def test_a_phone_at_the_face_is_a_call_even_when_the_ear_is_turned_away_and_the_hand_is_hidden():
    kp, kc = pose()
    kc[3] = 0.0  # left ear hidden (profile)
    kc[9] = 0.0  # the hand holding the phone is hidden behind the head
    assert phone_use(PERSON, kp, kc, [box_at(185, 108)])["kind"] == CALL


def test_a_hand_beside_a_profile_face_with_one_ear_hidden_still_counts_as_at_the_head():
    kp, kc = pose(L_WRI=(185, 120), L_ELB=(150, 200))
    kc[3] = 0.0
    assert phone_use(PERSON, kp, kc, [])["kind"] == POSSIBLE_CALL


def test_a_bowed_head_does_not_shrink_the_distance_limit():
    kp, kc = pose()
    kp[3], kp[4] = (192, 100), (208, 100)  # ears only 16 px apart, as when the head is tilted down
    kp[9] = (140, 300)
    assert phone_use(PERSON, kp, kc, [box_at(170, 300)])["kind"] == PHONE_IN_HAND  # phone 30 px from the wrist: within a tenth-of-height ruler


def shown_over_time(script):
    mon = FakeMonitor(script)
    shown = []
    for n in range(len(script)):
        mon.update(n * 0.25, None)
        shown.append(bool(mon.active()))
    return shown


def test_the_box_does_not_flicker_when_one_look_misses():
    on, off = [CALLING], [[]]
    shown = shown_over_time([on] * 4 + off + [on] * 3)
    assert shown[2:] == [True] * 6  # on from the third hit, and one missed look does not switch it off


def test_the_box_goes_away_once_the_person_has_clearly_stopped():
    shown = shown_over_time([[CALLING]] * 4 + [[]] * 5)
    assert shown[3] is True and shown[-1] is False


def test_the_box_glides_instead_of_jumping():
    a, b = {**CALLING, "box": (100, 60, 300, 400)}, {**CALLING, "box": (140, 60, 340, 400)}
    mon = FakeMonitor([[a], [b]])
    mon.update(0.0, None)
    mon.update(0.25, None)
    assert mon._last[7]["box"][0] == 120  # halfway between 100 and 140


def test_drawing_changes_the_picture_for_a_seen_phone_and_skips_a_small_guess():
    from ppe.phone import draw_findings

    blank = np.zeros((500, 400, 3), np.uint8)
    seen = {**CALLING, "box": (100, 60, 300, 400)}
    small_guess = {**CALLING, "kind": POSSIBLE_CALL, "needs_review": True, "box": (100, 60, 160, 160)}
    assert draw_findings(blank, [seen]).any()
    assert not draw_findings(blank, [small_guess]).any()  # a 100 px person's raised hand is not drawn
    assert draw_findings(blank, [{**small_guess, "box": (100, 60, 300, 400)}]).any()  # a tall person's is, in amber
