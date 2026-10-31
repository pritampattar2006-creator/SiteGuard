import numpy as np

from ppe.appearance import DressBook, signature, similarity
from ppe.faces import FaceGallery
from ppe.identify import FrameNamer
from ppe.people import PersonRegistry
from ppe.types import AnalysisResult, Detection, WorkerMatch

BOX = (100, 50, 200, 350)  # 100 x 300 person


def dressed(shirt, trousers, vest=None):
    """A grey picture with one person: BGR shirt colour, BGR trousers colour, optionally a hi-vis vest over the shirt."""
    image = np.full((400, 400, 3), 128, np.uint8)
    image[50 + int(0.20 * 300): 50 + int(0.57 * 300), 100:200] = shirt
    image[50 + int(0.57 * 300): 50 + int(0.95 * 300), 100:200] = trousers
    if vest is not None:
        image[50 + int(0.28 * 300): 50 + int(0.45 * 300), 125:175] = vest
    return image


RED, BLUE, BROWN, BLACK = (30, 30, 200), (200, 60, 30), (30, 80, 120), (20, 20, 20)
YELLOW_VEST = (0, 230, 230)


def test_the_same_clothes_look_the_same_and_different_clothes_do_not():
    a = signature(dressed(RED, BLUE), BOX)
    b = signature(dressed(RED, BLUE), BOX)
    c = signature(dressed(BLUE, BROWN), BOX)
    assert similarity(a, b) > 0.99
    assert similarity(a, c) < 0.8


def test_a_hi_vis_vest_does_not_change_the_signature():
    plain = signature(dressed(RED, BLUE), BOX)
    with_vest = signature(dressed(RED, BLUE, vest=YELLOW_VEST), BOX)
    assert similarity(plain, with_vest) > 0.95


def test_a_person_cut_off_by_the_edge_or_too_small_gives_no_signature():
    assert signature(dressed(RED, BLUE), (100, 50, 200, 399)) is None
    assert signature(dressed(RED, BLUE), (100, 50, 120, 90)) is None


def test_the_book_says_match_unknown_or_ambiguous(tmp_path):
    book = DressBook(tmp_path / "d.json")
    red, blue = signature(dressed(RED, BLUE), BOX), signature(dressed(BLUE, BROWN), BOX)
    assert book.match(red) == (None, "unknown")  # an empty book knows nobody
    book.add("E001", red)
    assert book.match(signature(dressed(RED, BLUE), BOX)) == ("E001", "match")
    assert book.match(blue)[1] == "unknown"
    book.add("E002", signature(dressed((40, 40, 205), BLUE), BOX))  # a near-identical outfit on someone else
    assert book.match(signature(dressed(RED, BLUE), BOX))[1] in ("ambiguous", "match")


def test_yesterdays_clothes_are_forgotten(tmp_path):
    book = DressBook(tmp_path / "d.json")
    book.add("E001", signature(dressed(RED, BLUE), BOX))
    book._day = "2000-01-01"  # as if the book was written long ago
    book._save()
    assert DressBook(tmp_path / "d.json").match(signature(dressed(RED, BLUE), BOX))[1] == "unknown"


class NoFaces:
    def detect(self, image):
        return []


def namer_for(tmp_path, book, registry=None):
    registry = registry or PersonRegistry(tmp_path / "p.json")  # the real service shares one registry between all uploads
    return FrameNamer(NoFaces(), FaceGallery(tmp_path / "g.json"), registry, "clip", "Gate 2", dummy_names=True, dress=book)


def result_for(boxes, ids):
    people = [Detection("person", 0.9, b, i) for b, i in zip(boxes, ids)]
    return AnalysisResult([], [WorkerMatch(i, p, None, None) for p, i in zip(people, ids)], [], False, (400, 400))


def watch(namer, image, worker_id=1):
    for n in range(3):
        namer.update(image, result_for([BOX], [worker_id]), None, n)


def test_someone_with_no_face_and_clothes_like_nobody_gets_a_new_made_up_identity(tmp_path):
    book = DressBook(tmp_path / "d.json")
    namer = namer_for(tmp_path, book)
    watch(namer, dressed(RED, BLUE))
    who = namer.settle(1)
    assert who is not None and who.dummy and who.employee_id == "E001"


def test_the_same_footage_seen_again_gets_the_same_identity(tmp_path):
    book = DressBook(tmp_path / "d.json")
    shared = PersonRegistry(tmp_path / "p.json")
    first = namer_for(tmp_path, book, shared)
    watch(first, dressed(RED, BLUE))
    a = first.settle(1)
    second = namer_for(tmp_path, book, shared)  # a second upload of the same scene, with a new track number
    watch(second, dressed(RED, BLUE), worker_id=77)
    b = second.settle(77)
    assert a.employee_id == b.employee_id


def test_two_different_outfits_become_two_different_people(tmp_path):
    book = DressBook(tmp_path / "d.json")
    shared = PersonRegistry(tmp_path / "p.json")
    n1, n2 = namer_for(tmp_path, book, shared), namer_for(tmp_path, book, shared)
    watch(n1, dressed(RED, BLUE))
    watch(n2, dressed(BLUE, BROWN))
    assert n1.settle(1).employee_id != n2.settle(1).employee_id


def test_someone_who_looks_like_two_known_people_is_left_unnamed(tmp_path):
    book = DressBook(tmp_path / "d.json")
    book.add("E001", signature(dressed(RED, BLUE), BOX))
    book.add("E002", signature(dressed((38, 36, 204), BLUE), BOX))
    namer = namer_for(tmp_path, book)
    watch(namer, dressed((34, 33, 202), BLUE))
    assert namer.settle(1) is None
