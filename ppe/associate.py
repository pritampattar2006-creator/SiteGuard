"""Decide which helmet and vest belong to which person. Pure Python: no model, no pixels.

This is the part that answers the problem statement's constraint: a helmet seen *somewhere* in the
image must not clear every worker. An item only counts for a worker when it sits in the body zone
where it is actually worn, and every item is given to at most one worker.
"""
from __future__ import annotations

from .config import Config
from .geometry import area, center, contains_point, fraction_inside, height, iou, width
from .types import Box, Detection, WorkerMatch

TIE_MARGIN = 0.02  # scores closer than this are treated as a tie
DUPLICATE_IOU = 0.5  # two same-class boxes overlapping more than this are one object seen twice


def head_zone(box: Box, cfg: Config) -> tuple[float, float, float, float]:
    h = height(box)
    return (box[0], box[1] - cfg.head_top_margin * h, box[2], box[1] + cfg.head_zone_frac * h)


def torso_zone(box: Box, cfg: Config) -> tuple[float, float, float, float]:
    h = height(box)
    return (box[0], box[1] + cfg.torso_top * h, box[2], box[1] + cfg.torso_bottom * h)


def _score(item: Box, zone, person: Box, covered: float) -> float:
    """60% how much of the item is in place, 40% how close it is to the middle of its zone."""
    zx, zy = center(zone)
    ix, iy = center(item)
    distance = ((ix - zx) ** 2 + (iy - zy) ** 2) ** 0.5 / max(height(person), 1.0)
    return 0.6 * covered + 0.4 * (1.0 - min(max(distance, 0.0), 1.0))


def _helmet_candidates(persons: list[Detection], helmets: list[Detection], cfg: Config) -> dict[tuple[int, int], float]:
    pairs: dict[tuple[int, int], float] = {}
    for pi, person in enumerate(persons):
        zone = head_zone(person.box, cfg)
        side = cfg.head_x_margin * width(person.box)
        for hi, helmet in enumerate(helmets):
            covered = fraction_inside(helmet.box, zone)
            centred = zone[0] + side <= center(helmet.box)[0] <= zone[2] - side
            if centred and contains_point(zone, center(helmet.box)) and covered >= cfg.helmet_min_in_zone:
                pairs[(pi, hi)] = _score(helmet.box, zone, person.box, covered)
    return pairs


def _vest_candidates(persons: list[Detection], vests: list[Detection], cfg: Config) -> dict[tuple[int, int], float]:
    pairs: dict[tuple[int, int], float] = {}
    for pi, person in enumerate(persons):
        zone = torso_zone(person.box, cfg)
        for vi, vest in enumerate(vests):
            covered = fraction_inside(vest.box, person.box)
            big_enough = (
                width(vest.box) >= cfg.vest_min_width_ratio * width(person.box)
                and height(vest.box) >= cfg.vest_min_height_ratio * height(person.box)
            )
            if contains_point(zone, center(vest.box)) and covered >= cfg.vest_min_in_person and big_enough:
                pairs[(pi, vi)] = _score(vest.box, zone, person.box, covered)
    return pairs


EXTRA_ITEMS = ("goggles", "gloves", "boots")
MULTI_ITEMS = ("gloves", "boots")  # a worker wears more than one, so one worker may own several detections


def item_conf(item: str, cfg: Config) -> float:
    return getattr(cfg, f"{item}_conf")


def extra_zone(item: str, person: Box, cfg: Config) -> tuple[float, float, float, float]:
    margin, top, bottom, _ = getattr(cfg, f"{item}_zone")
    w, h = width(person), height(person)
    return (person[0] - margin * w, person[1] + top * h, person[2] + margin * w, person[1] + bottom * h)


def _extra_candidates(item: str, persons: list[Detection], items: list[Detection], cfg: Config) -> dict[tuple[int, int], float]:
    min_cover = getattr(cfg, f"{item}_zone")[3]
    pairs: dict[tuple[int, int], float] = {}
    for pi, person in enumerate(persons):
        zone = extra_zone(item, person.box, cfg)
        for ii, det in enumerate(items):
            covered = fraction_inside(det.box, zone)
            if contains_point(zone, center(det.box)) and covered >= min_cover:
                pairs[(pi, ii)] = _score(det.box, zone, person.box, covered)
    return pairs


def _assign_many(persons: list[Detection], candidates: dict[tuple[int, int], float]) -> dict[int, list[int]]:
    """Every item goes to its single best worker, but a worker may own several (two gloves, two boots)."""
    scores_by_item: dict[int, dict[int, float]] = {}
    for (pi, ii), score in candidates.items():
        scores_by_item.setdefault(ii, {})[pi] = score
    owners: dict[int, list[int]] = {}
    for ii, scores in scores_by_item.items():
        best = max(scores.values())
        near = [pi for pi, s in scores.items() if best - s < TIE_MARGIN]
        owners.setdefault(min(near, key=lambda pi: area(persons[pi].box)), []).append(ii)
    return owners


def _assign(persons: list[Detection], candidates: dict[tuple[int, int], float]) -> dict[int, int]:
    """One-to-one, best score first. Returns {person index: item index}.

    If an item scores almost the same for two people, it goes to the one with the smaller box:
    the larger box is more likely a merged or oversized detection.
    """
    assigned: dict[int, int] = {}
    remaining = dict(candidates)
    while remaining:
        (_, item), best = max(remaining.items(), key=lambda kv: kv[1])
        near = [pi for (pi, ii), s in remaining.items() if ii == item and best - s < TIE_MARGIN]
        person = min(near, key=lambda pi: area(persons[pi].box))
        assigned[person] = item
        remaining = {k: s for k, s in remaining.items() if k[0] != person and k[1] != item}
    return assigned


def _human_shaped(box: Box, cfg: Config) -> bool:
    """Only people are judged: a box far wider than tall cannot be one."""
    h = height(box)
    return h > 0 and width(box) / h <= cfg.person_max_aspect


def _dedupe(detections: list[Detection]) -> list[Detection]:
    """Keep the most confident box when the same object was detected twice."""
    kept: list[Detection] = []
    for det in sorted(detections, key=lambda d: -d.conf):
        if all(iou(det.box, k.box) <= DUPLICATE_IOU for k in kept):
            kept.append(det)
    return kept


def _split_by_strength(detections: list[Detection], label: str, strong_conf: float, cfg: Config):
    """Return (strong, weak): at/above the class confidence, and between the weak floor and it."""
    found = _dedupe([d for d in detections if d.label == label and d.conf >= min(cfg.weak_conf_floor, strong_conf)])
    return [d for d in found if d.conf >= strong_conf], [d for d in found if d.conf < strong_conf]


def _weak_owners(persons, weak_items, candidates, strong_of) -> set[int]:
    """Indices of persons with no confident item who do have a weak one in the right zone."""
    pairs = {key: score for key, score in candidates(persons, weak_items).items() if key[0] not in strong_of}
    return set(_assign(persons, pairs))


def _flags(person: Detection, others: list[Detection], image_size: tuple[int, int], cfg: Config) -> list[str]:
    image_h = image_size[1]
    x1, y1, x2, y2 = person.box
    flags = []
    if height(person.box) < max(cfg.tiny_min_height_px, cfg.tiny_min_height_frac * image_h):
        flags.append("tiny")
    if y1 <= cfg.edge_margin_frac * image_h:
        flags.append("edge_top")
    if y2 >= image_h * (1 - cfg.edge_margin_frac):
        flags.append("edge_bottom")  # the feet are cut off
        if width(person.box) > 0 and height(person.box) / width(person.box) < cfg.torso_min_aspect:
            flags.append("torso_cut")  # so little of the body is visible that the torso is cut off too
    if person.conf < cfg.low_person_conf:
        flags.append("low_conf")
    if any(iou(person.box, other.box) > cfg.crowded_iou for other in others):
        flags.append("crowded")
    if height(person.box) > 0 and width(person.box) / height(person.box) > cfg.wide_box_ratio:
        flags.append("wide_box")
    if height(person.box) < max(cfg.detail_min_height_px, cfg.detail_min_height_frac * image_h):
        flags.append("small_detail")
    return flags


def down_candidates(detections: list[Detection], cfg: Config) -> list[Detection]:
    """Person boxes far wider than tall. A standing, sitting or bending person is never that wide, so this is either a
    machine or pile mistaken for a person, or someone lying on the ground. Only a check is raised, never a verdict."""
    out = []
    for d in detections:
        if d.label == "person" and d.conf >= cfg.down_min_conf and height(d.box) > 0:
            aspect = width(d.box) / height(d.box)
            if cfg.person_max_aspect < aspect <= cfg.down_max_aspect:
                out.append(d)
    return out


def _bare_head_owners(persons, helmet_of: dict[int, int], helmets, detections, cfg: Config) -> set[int]:
    """Workers whose head zone holds a convincing bare or covered head. Where a helmet was matched to the same head and the
    head is the more confident of the two, the "helmet" was a cap, beanie or head cloth: the helmet is cancelled."""
    heads = _dedupe([d for d in detections if d.label == "head" and d.conf >= cfg.head_conf])
    bare: set[int] = set()
    for pi, person in enumerate(persons):
        zone = head_zone(person.box, cfg)
        side = cfg.head_x_margin * width(person.box)
        here = [h for h in heads if zone[0] + side <= center(h.box)[0] <= zone[2] - side and contains_point(zone, center(h.box))]
        if not here:
            continue
        best = max(here, key=lambda h: h.conf)
        if pi in helmet_of:
            helmet = helmets[helmet_of[pi]]
            if best.conf >= helmet.conf and iou(best.box, helmet.box) >= 0.3:
                del helmet_of[pi]
                bare.add(pi)
        else:
            bare.add(pi)
    return bare


def associate(
    detections: list[Detection], image_size: tuple[int, int], cfg: Config
) -> tuple[list[WorkerMatch], list[Detection]]:
    """Return one WorkerMatch per person (left to right) and every helmet/vest nobody is wearing.

    `image_size` is (width, height).
    """
    persons = [d for d in detections if d.label == "person" and d.conf >= cfg.person_conf and _human_shaped(d.box, cfg)]
    helmets, weak_helmets = _split_by_strength(detections, "helmet", cfg.helmet_conf, cfg)
    vests, weak_vests = _split_by_strength(detections, "vest", cfg.vest_conf, cfg)
    persons.sort(key=lambda d: center(d.box)[0])

    helmet_of = _assign(persons, _helmet_candidates(persons, helmets, cfg))
    vest_of = _assign(persons, _vest_candidates(persons, vests, cfg))
    bare_owners = _bare_head_owners(persons, helmet_of, helmets, detections, cfg)
    weak_helmet_owners = _weak_owners(persons, weak_helmets, lambda p, i: _helmet_candidates(p, i, cfg), helmet_of) - bare_owners
    weak_vest_owners = _weak_owners(persons, weak_vests, lambda p, i: _vest_candidates(p, i, cfg), vest_of)

    # Extra equipment (goggles / gloves / boots), only for the items this site actually requires.
    extras_of: dict[str, dict[int, list[int]]] = {}
    extras_found: dict[str, list[Detection]] = {}
    weak_extra_owners: dict[str, set[int]] = {}
    for item in (i for i in EXTRA_ITEMS if i in cfg.required):
        strong, weak = _split_by_strength(detections, item, item_conf(item, cfg), cfg)
        candidates = _extra_candidates(item, persons, strong, cfg)
        owners = _assign_many(persons, candidates) if item in MULTI_ITEMS else {pi: [ii] for pi, ii in _assign(persons, candidates).items()}
        extras_found[item], extras_of[item] = strong, owners
        weak_extra_owners[item] = _weak_owners(persons, weak, lambda p, i, item=item: _extra_candidates(item, p, i, cfg), owners)

    matches = []
    for pi, person in enumerate(persons):
        others = [p for j, p in enumerate(persons) if j != pi]
        flags = _flags(person, others, image_size, cfg)
        if pi in weak_helmet_owners:
            flags.append("weak_helmet")
        if pi in weak_vest_owners:
            flags.append("weak_vest")
        if pi in bare_owners:
            flags.append("bare_head")
        flags += [f"weak_{item}" for item, owners in weak_extra_owners.items() if pi in owners]
        matches.append(
            WorkerMatch(
                worker_id=person.track_id if person.track_id is not None else pi + 1,
                person=person,
                helmet=helmets[helmet_of[pi]] if pi in helmet_of else None,
                vest=vests[vest_of[pi]] if pi in vest_of else None,
                flags=flags,
                extras={item: [extras_found[item][ii] for ii in owners.get(pi, [])] for item, owners in extras_of.items()},
            )
        )

    used_helmets = set(helmet_of.values())
    used_vests = set(vest_of.values())
    unassigned = [h for i, h in enumerate(helmets) if i not in used_helmets]
    unassigned += [v for i, v in enumerate(vests) if i not in used_vests]
    for item, owners in extras_of.items():
        used = {ii for items in owners.values() for ii in items}
        unassigned += [d for i, d in enumerate(extras_found[item]) if i not in used]
    return matches, unassigned
