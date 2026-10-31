from ppe.track import stitch_tracks


def box(x, y=100, w=40, h=120):
    return (x, y, x + w, y + h)


def test_a_person_who_gets_a_new_number_after_being_lost_is_joined_up():
    tracks = {1: {"first": 0, "last": 20, "first_box": box(100), "last_box": box(130)}, 7: {"first": 24, "last": 60, "first_box": box(135), "last_box": box(200)}}
    assert stitch_tracks(tracks, gap_frames=45) == {7: 1}


def test_two_people_in_the_same_picture_are_never_joined():
    tracks = {1: {"first": 0, "last": 50, "first_box": box(100), "last_box": box(110)}, 2: {"first": 10, "last": 60, "first_box": box(120), "last_box": box(130)}}
    assert stitch_tracks(tracks, gap_frames=45) == {}


def test_a_new_number_far_away_or_much_later_is_a_different_person():
    far = {1: {"first": 0, "last": 20, "first_box": box(100), "last_box": box(130)}, 2: {"first": 24, "last": 60, "first_box": box(600), "last_box": box(610)}}
    late = {1: {"first": 0, "last": 20, "first_box": box(100), "last_box": box(130)}, 2: {"first": 200, "last": 260, "first_box": box(135), "last_box": box(140)}}
    assert stitch_tracks(far, gap_frames=45) == {} and stitch_tracks(late, gap_frames=45) == {}


def test_a_much_bigger_or_smaller_person_is_a_different_person():
    tracks = {1: {"first": 0, "last": 20, "first_box": box(100), "last_box": box(130)}, 2: {"first": 24, "last": 60, "first_box": box(135, y=100, w=100, h=300), "last_box": box(140, y=100, w=100, h=300)}}
    assert stitch_tracks(tracks, gap_frames=45) == {}


def test_a_chain_of_new_numbers_is_all_one_person():
    tracks = {1: {"first": 0, "last": 10, "first_box": box(100), "last_box": box(110)}, 5: {"first": 14, "last": 30, "first_box": box(115), "last_box": box(125)},
              9: {"first": 34, "last": 50, "first_box": box(130), "last_box": box(140)}}
    assert stitch_tracks(tracks, gap_frames=45) == {5: 1, 9: 1}


def test_two_new_numbers_starting_near_one_lost_person_do_not_both_take_over_that_person():
    tracks = {1: {"first": 0, "last": 20, "first_box": box(100), "last_box": box(130)}, 2: {"first": 24, "last": 90, "first_box": box(135), "last_box": box(150)},
              3: {"first": 26, "last": 90, "first_box": box(140), "last_box": box(170)}}
    joined = stitch_tracks(tracks, gap_frames=45)
    assert not (joined.get(2) == 1 and joined.get(3) == 1)  # 2 and 3 are in the same picture: at most one of them is person 1
