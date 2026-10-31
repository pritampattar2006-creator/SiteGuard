import numpy as np

from ppe.types import Detection
from ppe.verify import PersonVerifier, helmet_blob_ratio


class Fake(PersonVerifier):
    """A verifier whose second opinion is scripted, so no models are loaded."""

    def __init__(self, sees, **kw):
        super().__init__(**kw)
        self.sees = list(sees)
        self.asked = 0

    def _sees_person(self, crop):
        self.asked += 1
        return self.sees.pop(0) if len(self.sees) > 1 else self.sees[0]


def photo():
    return np.full((600, 400, 3), 120, np.uint8)


def person(conf=0.5, track=None, box=(50, 100, 200, 500)):
    return Detection("person", conf, box, track)


def test_orange_blob_wider_than_a_helmet_is_noticed():
    crop = np.full((200, 100, 3), 100, np.uint8)
    crop[60:140, 10:90] = (0, 110, 255)  # BGR orange, 80% of the width
    assert helmet_blob_ratio(crop) > 0.6
    plain = np.full((200, 100, 3), 100, np.uint8)
    assert helmet_blob_ratio(plain) == 0.0


def test_a_photo_object_is_removed_when_neither_model_sees_a_body():
    v = Fake([False])
    kept, objects = v.screen(photo(), [person(0.5)])
    assert kept == [] and len(objects) == 1


def test_a_real_person_stays_when_the_second_check_finds_a_body():
    kept, objects = Fake([True]).screen(photo(), [person(0.5)])
    assert len(kept) == 1 and objects == []


def test_a_confident_person_is_not_even_rechecked():
    v = Fake([False])
    kept, _ = v.screen(photo(), [person(0.9)])
    assert len(kept) == 1 and v.asked == 0


def test_tiny_boxes_are_left_alone():
    v = Fake([False])
    kept, _ = v.screen(photo(), [person(0.4, box=(10, 10, 40, 60))])
    assert len(kept) == 1 and v.asked == 0


def test_a_helmet_coloured_blob_triggers_the_check_even_when_the_model_is_confident():
    image = photo()
    image[150:300, 60:190] = (0, 110, 255)
    v = Fake([False])
    kept, objects = v.screen(image, [person(0.9)])
    assert v.asked == 1 and objects


def test_video_track_needs_two_checks_to_become_an_object_and_then_stays_one():
    v = Fake([False, False, False])
    first = v.screen(photo(), [person(0.5, track=7)])
    assert len(first[0]) == 1  # one vote is not enough
    second = v.screen(photo(), [person(0.8, track=7)])  # even at high confidence, the latch holds
    assert second[1] and not second[0]
    third = v.screen(photo(), [person(0.9, track=7)])
    assert third[1]


def test_a_latched_track_is_released_after_two_checks_find_a_body():
    v = Fake([False, False, True, True])
    for _ in range(2):
        v.screen(photo(), [person(0.5, track=3)])
    assert v.screen(photo(), [person(0.5, track=3)])[1]  # one body sighting: still held
    assert v.screen(photo(), [person(0.5, track=3)])[0]  # two in a row: released


def test_other_labels_pass_through_untouched():
    helmet = Detection("helmet", 0.6, (60, 100, 90, 130))
    kept, objects = Fake([False]).screen(photo(), [helmet])
    assert kept == [helmet] and objects == []
