import time

import numpy as np
import pytest

from ppe import livefeed
from ppe.livefeed import LiveFeeds, check_address


@pytest.mark.parametrize("url", ["http://192.168.1.5:8080/video", "http://10.0.0.7/video", "rtsp://172.16.4.2:554/live", "http://127.0.0.1:8099/video", "http://localhost:8080/video"])
def test_cameras_on_the_local_network_are_accepted(url):
    assert check_address(url) == url


@pytest.mark.parametrize("url", ["http://8.8.8.8/video", "rtsp://93.184.216.34/live", "file:///C:/secret.mp4", "ftp://192.168.1.5/x", "not a url", "", "http:///video"])
def test_other_addresses_are_refused(url):
    with pytest.raises(ValueError):
        check_address(url)


class FakeCapture:
    def __init__(self, url):
        self.n = 0

    def isOpened(self):
        return True

    def set(self, prop, value):
        return True

    def grab(self):
        time.sleep(0.02)
        self.n += 1
        return True

    def retrieve(self):
        return True, np.full((90, 160, 3), self.n % 255, np.uint8)

    def release(self):
        pass


def test_the_live_loop_checks_frames_and_keeps_a_picture(monkeypatch):
    monkeypatch.setattr(livefeed.cv2, "VideoCapture", FakeCapture)
    seen = []

    def analyse(frame, options):
        seen.append(options["location"])
        return {"workers": [{"id": 1, "status": "VIOLATION", "missing": ["NO HELMET"]}], "pushed": 1, "repeats": 0, "_image": frame}

    feeds = LiveFeeds(analyse, every_s=0.05)
    feed_id = feeds.start("http://192.168.1.5:8080/video", {"location": "Gate 2"})
    for _ in range(100):
        state = feeds.status(feed_id)
        if state["analysed"] >= 2:
            break
        time.sleep(0.05)
    state = feeds.status(feed_id)
    assert state["status"] == "live" and state["analysed"] >= 2
    assert state["workers"][0]["missing"] == ["NO HELMET"] and state["pushed"] >= 2
    assert seen[0] == "Gate 2"
    assert feeds.jpg(feed_id)[:2] == b"\xff\xd8"  # a JPEG
    feeds.stop(feed_id)
    assert feeds.status(feed_id)["status"] == "stopped"


def test_a_camera_that_cannot_be_opened_ends_in_a_clear_error(monkeypatch):
    class Closed:
        def __init__(self, url): pass
        def isOpened(self): return False
        def release(self): pass

    monkeypatch.setattr(livefeed.cv2, "VideoCapture", Closed)
    monkeypatch.setattr(livefeed.time, "sleep", lambda s: None)
    feeds = LiveFeeds(lambda f, o: {})
    feed_id = feeds.start("http://192.168.1.5:8080/video", {})
    for _ in range(100):
        if feeds.status(feed_id)["status"] == "error":
            break
        time.sleep(0.02)
    assert feeds.status(feed_id)["status"] == "error"
    assert "same WiFi" in feeds.status(feed_id)["error"]


def test_each_sector_keeps_its_own_camera_and_a_new_one_replaces_only_that_sectors(monkeypatch):
    monkeypatch.setattr(livefeed.cv2, "VideoCapture", FakeCapture)
    feeds = LiveFeeds(lambda frame, options: {"workers": [], "pushed": 0, "repeats": 0, "_image": frame}, every_s=0.05)
    welding = feeds.start("http://192.168.1.5:8080/video", {"sector": "weld"})
    building = feeds.start("http://192.168.1.6:8080/video", {"sector": "build"})
    assert {f["sector"] for f in feeds.running()} == {"weld", "build"}  # both are on at once
    assert [f["id"] for f in feeds.running({"weld"})] == [welding]  # a supervisor asking for welding sees only welding
    newer = feeds.start("http://192.168.1.7:8080/video", {"sector": "weld"})
    assert [f["id"] for f in feeds.running({"weld"})] == [newer]  # replaced
    assert [f["id"] for f in feeds.running({"build"})] == [building]  # untouched
    feeds.stop_all()


def test_detections_are_drawn_on_the_newest_frame_not_the_old_one():
    old = np.full((90, 160, 3), 100, np.uint8)
    drawn = old.copy()
    drawn[10:20, 10:60] = (0, 0, 255)  # a box the detector drew
    overlay = livefeed.make_overlay(old, drawn)
    newer = np.full((90, 160, 3), 140, np.uint8)  # the camera has moved on
    shown = livefeed.compose(newer, overlay)
    assert (shown[15, 30] == (0, 0, 255)).all()  # the box is on the new picture
    assert (shown[60, 100] == 140).all()  # and the rest of it is the new picture, not the old one
    assert (newer[15, 30] == 140).all()  # the new frame itself was not changed


def test_no_detections_or_a_changed_picture_size_leaves_the_frame_alone():
    frame = np.full((90, 160, 3), 100, np.uint8)
    assert livefeed.compose(frame, None) is frame
    assert livefeed.make_overlay(frame, np.zeros((50, 50, 3), np.uint8)) is None
    big = np.zeros((90, 200, 3), np.uint8)
    assert livefeed.compose(big, (np.ones((90, 160), bool), frame)) is big


def test_a_wide_phone_frame_is_shrunk_to_the_width_used_for_checking():
    assert livefeed.fit_width(np.zeros((1080, 1920, 3), np.uint8)).shape == (720, 1280, 3)
    small = np.zeros((90, 160, 3), np.uint8)
    assert livefeed.fit_width(small) is small


def person(shoulder_y, hip_y, shoulder_x=100.0, hip_x=100.0, nose=None):
    """One person's 17 pose points with only shoulders, hips and (optionally) the nose set, all confident."""
    kp = np.zeros((17, 2), float)
    kc = np.zeros(17, float)
    for i, xy in ((5, (shoulder_x - 15, shoulder_y)), (6, (shoulder_x + 15, shoulder_y)), (11, (hip_x - 10, hip_y)), (12, (hip_x + 10, hip_y))):
        kp[i], kc[i] = xy, 0.9
    if nose:
        kp[0], kc[0] = nose, 0.9
    return kp, kc


def count(*people):
    return livefeed.upright_count(np.array([p[0] for p in people]), np.array([p[1] for p in people]))


def test_people_standing_head_up_are_counted_and_lying_or_upside_down_ones_are_not():
    assert count(person(100, 200), person(120, 230)) == 2  # shoulders above hips
    assert count(person(200, 100)) == 0  # upside down
    assert count(person(150, 150, shoulder_x=60, hip_x=160)) == 0  # on their side: the line is horizontal


def test_without_hips_the_nose_above_the_shoulders_counts_as_head_up():
    kp, kc = person(100, 200, nose=(100, 60))
    kc[11] = kc[12] = 0.0
    assert livefeed.upright_count(np.array([kp]), np.array([kc])) == 1


def test_the_turn_with_most_upright_people_wins_and_ties_keep_the_picture_as_it_is():
    assert livefeed.pick_rotation({0: 0, 90: 0, 180: 0, 270: 0}, 0) is None  # nobody seen: no change
    assert livefeed.pick_rotation({0: 0, 90: 3, 180: 0, 270: 1}, 0) == 90
    assert livefeed.pick_rotation({0: 2, 90: 2, 180: 0, 270: 0}, 90) == 90  # tied, and the current one is among the best
    assert livefeed.pick_rotation({0: 2, 90: 2, 180: 0, 270: 0}, 180) is None  # tied, current is not among them: undecided


def test_rotating_a_frame_clockwise_swaps_its_sides():
    frame = np.zeros((2, 4, 3), np.uint8)
    frame[0, 0] = 255  # top-left pixel
    assert livefeed.rotate_frame(frame, 0) is frame
    turned = livefeed.rotate_frame(frame, 90)
    assert turned.shape[:2] == (4, 2) and turned[0, 1].all()  # top-left goes to top-right
    assert livefeed.rotate_frame(frame, 180)[1, 3].all()
