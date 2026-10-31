from ppe.detector import fuse_detections
from ppe.types import Detection


def test_boxes_both_models_agree_on_get_the_average_confidence_and_box():
    a, b = Detection("helmet", 0.8, (100, 100, 200, 200)), Detection("helmet", 0.6, (104, 104, 204, 204))
    [fused] = fuse_detections([a], [b])
    assert fused.conf == 0.7 and fused.box == (102, 102, 202, 202)


def test_a_box_only_one_model_sees_keeps_half_its_confidence():
    only_a, only_b = Detection("vest", 0.8, (0, 0, 50, 50)), Detection("vest", 0.6, (500, 500, 560, 560))
    fused = fuse_detections([only_a], [only_b])
    assert sorted(round(d.conf, 2) for d in fused) == [0.3, 0.4]


def test_different_classes_never_fuse():
    fused = fuse_detections([Detection("helmet", 0.8, (0, 0, 50, 50))], [Detection("vest", 0.8, (0, 0, 50, 50))])
    assert len(fused) == 2 and all(d.conf == 0.4 for d in fused)


def test_each_box_is_used_once():
    a = [Detection("person", 0.9, (0, 0, 100, 200)), Detection("person", 0.8, (2, 2, 102, 202))]
    b = [Detection("person", 0.7, (1, 1, 101, 201))]
    assert len(fuse_detections(a, b)) == 2
