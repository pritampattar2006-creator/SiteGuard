"""Association tests on hand-made boxes (no model). Each test is one sentence you can say to a judge.

Default worker: 100 px wide, 300 px tall, top at y=100 in a 1000x1000 image, so
head zone  = y  70..205 and torso zone = y 160..295.
"""
from ppe.associate import associate
from ppe.config import Config
from ppe.types import Detection

CFG = Config()
SIZE = (1000, 1000)


def person(x=0, top=100, w=100, h=300, conf=0.9, track_id=None):
    return Detection("person", conf, (x, top, x + w, top + h), track_id)


def helmet(x, y, w=50, h=40):
    return Detection("helmet", 0.9, (x, y, x + w, y + h))


def vest(x, y, w=90, h=100):
    return Detection("vest", 0.9, (x, y, x + w, y + h))


def worn_helmet(p):
    return helmet(p.box[0] + 25, p.box[1] + 5)


def worn_vest(p):
    return vest(p.box[0] + 5, p.box[1] + 70)


def run(*detections):
    return associate(list(detections), SIZE, CFG)


def test_helmet_on_the_head_is_assigned():
    p = person()
    [m], unassigned = run(p, worn_helmet(p))
    assert m.helmet is not None and unassigned == []


def test_helmet_held_at_waist_height_is_not_assigned():
    p = person()
    hand = helmet(40, 250)
    [m], unassigned = run(p, hand)
    assert m.helmet is None and unassigned == [hand]


def test_helmet_far_from_every_person_is_unassigned():
    p = person()
    table = helmet(500, 600)
    [m], unassigned = run(p, table)
    assert m.helmet is None and unassigned == [table]


def test_one_helmet_between_two_overlapping_heads_goes_to_exactly_one_worker():
    a, b = person(0), person(60)
    [ma, mb], unassigned = run(a, b, helmet(45, 105))
    assert [ma.helmet is not None, mb.helmet is not None].count(True) == 1
    assert unassigned == []


def test_two_workers_each_get_their_own_helmet():
    a, b = person(0), person(400)
    [ma, mb], _ = run(a, b, worn_helmet(a), worn_helmet(b))
    assert ma.helmet == worn_helmet(a) and mb.helmet == worn_helmet(b)


def test_near_tie_goes_to_the_smaller_box():
    big, small = person(0, h=300), person(0, h=280)
    [m_big, m_small], _ = run(big, small, helmet(25, 105))
    assert m_big.helmet is None and m_small.helmet is not None


def test_a_neighbours_helmet_at_the_edge_of_an_oversized_box_is_not_credited():
    big = person(0, w=500, h=1000)  # a box that swallows the people standing beside the worker
    neighbour_helmet = helmet(440, 110)  # at the far right edge of the big box, inside its head zone
    [m], unassigned = run(big, neighbour_helmet)
    assert m.helmet is None and unassigned == [neighbour_helmet]


def test_a_helmet_in_the_middle_of_a_wide_box_is_still_credited():
    wide = person(0, w=500, h=1000)
    [m], _ = run(wide, helmet(225, 110))
    assert m.helmet is not None


def test_a_seated_workers_lower_vest_is_still_assigned():
    p = person()
    low_vest = vest(5, 205)  # centre at 255 = 52% down the box: lower than a standing worker's, as when sitting
    [m], _ = run(p, low_vest)
    assert m.vest is not None


def test_vest_on_the_torso_is_assigned():
    p = person()
    [m], _ = run(p, worn_vest(p))
    assert m.vest is not None


def test_vest_that_is_too_small_is_not_assigned():
    p = person()
    patch = vest(30, 200, w=30, h=30)
    [m], unassigned = run(p, patch)
    assert m.vest is None and unassigned == [patch]


def test_vest_outside_the_torso_band_is_not_assigned():
    p = person()
    on_head = vest(5, 90)
    [m], _ = run(p, on_head)
    assert m.vest is None


def test_one_vest_overlapping_two_people_goes_to_only_one():
    a, b = person(0), person(80)
    [ma, mb], _ = run(a, b, vest(40, 170))
    assert [ma.vest is not None, mb.vest is not None].count(True) == 1


def test_low_confidence_detections_are_dropped():
    p = person()
    weak_helmet = Detection("helmet", 0.1, worn_helmet(p).box)
    [m], unassigned = run(p, weak_helmet)
    assert m.helmet is None and unassigned == []


def test_weak_helmet_on_the_head_flags_the_worker_instead_of_crediting_them():
    p = person()
    weak = Detection("helmet", 0.2, worn_helmet(p).box)  # between the weak floor (0.15) and 0.30
    [m], unassigned = run(p, weak)
    assert m.helmet is None and "weak_helmet" in m.flags and unassigned == []


def test_weak_helmet_is_ignored_when_a_confident_one_is_present():
    p = person()
    [m], _ = run(p, worn_helmet(p), Detection("helmet", 0.2, (30, 110, 70, 140)))
    assert m.helmet is not None and "weak_helmet" not in m.flags


def test_weak_helmet_far_from_the_worker_does_not_flag_them():
    p = person()
    [m], _ = run(p, Detection("helmet", 0.2, (500, 600, 550, 640)))
    assert "weak_helmet" not in m.flags


def test_detections_below_the_weak_floor_are_ignored():
    p = person()
    [m], _ = run(p, Detection("helmet", 0.05, worn_helmet(p).box))
    assert "weak_helmet" not in m.flags


def test_duplicate_detection_of_one_helmet_is_not_reported_as_unassigned():
    p = person()
    strong, duplicate = worn_helmet(p), Detection("helmet", 0.35, (26, 106, 74, 146))
    [m], unassigned = run(p, strong, duplicate)
    assert m.helmet == strong and unassigned == []


def test_a_box_far_wider_than_tall_is_not_a_person():
    machine = Detection("person", 0.9, (0, 400, 600, 500))  # 600 wide, 100 tall
    assert run(machine) == ([], [])


def test_a_wide_but_human_shaped_box_is_still_judged():
    bending = person(w=260, h=300)  # bent over: wider than a standing worker, still a person
    [m], _ = run(bending)
    assert m.person is bending


def test_flag_tiny():
    [m], _ = run(person(top=500, h=60))
    assert "tiny" in m.flags


def test_flag_edge_top():
    [m], _ = run(person(top=10))
    assert "edge_top" in m.flags


def test_flag_edge_bottom():
    [m], _ = run(person(top=700))
    assert "edge_bottom" in m.flags


def test_a_tall_box_cut_off_at_the_feet_still_shows_the_torso():
    [m], _ = run(person(top=700))  # 100 wide, 300 tall, reaching the bottom of the photo
    assert "edge_bottom" in m.flags and "torso_cut" not in m.flags


def test_a_short_box_cut_off_at_the_bottom_has_its_torso_cut_too():
    [m], _ = run(person(top=800, w=150, h=200))  # barely taller than it is wide: only the upper body is in view
    assert "edge_bottom" in m.flags and "torso_cut" in m.flags


def test_flag_low_conf():
    [m], _ = run(person(conf=0.40))
    assert "low_conf" in m.flags


def test_flag_crowded():
    ms, _ = run(person(0), person(30))
    assert all("crowded" in m.flags for m in ms)


def test_flag_wide_box():
    [m], _ = run(person(w=450))  # 1.5 times wider than tall: probably several people merged
    assert "wide_box" in m.flags


def test_a_seated_or_bending_worker_is_not_flagged_as_a_wide_box():
    [m], _ = run(person(w=360))  # 1.2 times wider than tall
    assert "wide_box" not in m.flags


def test_a_cap_read_as_a_helmet_is_overruled_by_a_more_convincing_head():
    p = person()
    cap = Detection("helmet", 0.5, worn_helmet(p).box)
    head = Detection("head", 0.7, worn_helmet(p).box)
    [m], _ = run(p, cap, head)
    assert m.helmet is None and "bare_head" in m.flags


def test_a_helmet_more_convincing_than_the_head_still_counts():
    p = person()
    helmet_det = Detection("helmet", 0.8, worn_helmet(p).box)
    head = Detection("head", 0.5, worn_helmet(p).box)
    [m], _ = run(p, helmet_det, head)
    assert m.helmet is not None and "bare_head" not in m.flags


def test_a_bare_head_alone_is_flagged_even_with_no_helmet_detection():
    p = person()
    [m], _ = run(p, Detection("head", 0.6, worn_helmet(p).box))
    assert m.helmet is None and "bare_head" in m.flags


def test_a_head_outside_this_workers_head_zone_is_ignored():
    p = person()
    [m], _ = run(p, Detection("head", 0.9, (600, 600, 650, 650)))
    assert "bare_head" not in m.flags


def test_a_person_box_far_wider_than_tall_is_a_down_candidate_not_a_worker():
    from ppe.associate import down_candidates

    lying = Detection("person", 0.8, (0, 400, 400, 500))  # 4 times wider than tall
    assert down_candidates([lying, person()], CFG) == [lying]
    assert run(lying) == ([], [])  # and it is not judged for PPE


def test_down_candidates_need_confidence_and_a_really_wide_box():
    from ppe.associate import down_candidates

    assert down_candidates([Detection("person", 0.3, (0, 400, 400, 500))], CFG) == []
    assert down_candidates([Detection("person", 0.9, (0, 400, 150, 500))], CFG) == []  # 1.5: bending, not lying


def test_clean_worker_has_no_flags():
    [m], _ = run(person())
    assert m.flags == []


def test_worker_ids_run_left_to_right():
    ms, _ = run(person(500), person(0))
    assert [m.person.box[0] for m in ms] == [0, 500]
    assert [m.worker_id for m in ms] == [1, 2]


def test_track_id_is_used_as_worker_id_when_present():
    [m], _ = run(person(track_id=7))
    assert m.worker_id == 7


def test_empty_input():
    assert run() == ([], [])
