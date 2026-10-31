from ppe.detector import cut_by_tile_edge, merge_detections, tile_origins
from ppe.types import Detection


def test_tiles_cover_the_whole_image_and_overlap():
    tiles = tile_origins(1000, 800, grid=2, overlap=0.25)
    assert len(tiles) == 4
    assert min(t[0] for t in tiles) == 0 and max(t[0] + t[2] for t in tiles) == 1000
    assert min(t[1] for t in tiles) == 0 and max(t[1] + t[3] for t in tiles) == 800
    left, right = tiles[0], tiles[1]
    assert left[0] + left[2] > right[0]  # neighbouring tiles share some width


def test_a_box_sliced_by_an_inner_tile_edge_is_detected_as_cut():
    tile = (0, 0, 600, 500)  # left tile of a 1000-wide image: its right edge is an inner edge
    assert cut_by_tile_edge((520, 100, 600, 300), tile, 1000, 800) is True
    assert cut_by_tile_edge((0, 100, 80, 300), tile, 1000, 800) is False  # touches the image edge only
    assert cut_by_tile_edge((200, 100, 300, 300), tile, 1000, 800) is False


def test_duplicate_boxes_of_one_object_are_merged_keeping_the_most_confident():
    strong, weak = Detection("person", 0.9, (10, 10, 110, 210)), Detection("person", 0.5, (12, 12, 112, 212))
    assert merge_detections([weak, strong]) == [strong]


def test_a_half_box_inside_a_more_confident_box_of_the_same_class_is_dropped():
    whole, half = Detection("person", 0.9, (0, 0, 200, 400)), Detection("person", 0.6, (10, 0, 190, 180))
    assert merge_detections([half, whole]) == [whole]


def test_a_person_partly_behind_another_is_kept():
    front, behind = Detection("person", 0.9, (100, 100, 300, 500)), Detection("person", 0.7, (20, 60, 180, 400))
    assert len(merge_detections([front, behind])) == 2


def test_overlapping_boxes_of_different_classes_are_both_kept():
    person, vest = Detection("person", 0.9, (10, 10, 110, 210)), Detection("vest", 0.8, (15, 60, 105, 160))
    assert len(merge_detections([person, vest])) == 2


def test_two_separate_people_are_not_merged():
    a, b = Detection("person", 0.9, (0, 0, 100, 200)), Detection("person", 0.9, (300, 0, 400, 200))
    assert len(merge_detections([a, b])) == 2
