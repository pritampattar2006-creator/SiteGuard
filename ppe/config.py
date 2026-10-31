"""Every tunable number in one place. All values are starting points to be tuned on the evaluation set."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # Minimum detector confidence per class. Lower = more detections, more false alarms.
    person_conf: float = 0.35
    helmet_conf: float = 0.35  # was 0.30: on 314 held-out photos 0.35 removed 6 false helmets (caps, beanies) and lost only 2 real ones, which go to review
    vest_conf: float = 0.35

    # Extra equipment (needs the second model). Small items, so slightly lower confidence cut-offs.
    goggles_conf: float = 0.25
    gloves_conf: float = 0.30
    boots_conf: float = 0.30
    # Where each extra item is worn, as (sideways margin as a share of the person's width, top, bottom as a
    # share of the person's height from the top of the box, minimum share of the item that must sit in the zone).
    goggles_zone: tuple = (0.05, -0.05, 0.28, 0.5)
    gloves_zone: tuple = (0.30, 0.25, 0.85, 0.5)   # hands swing out sideways, so the zone is wider than the person
    boots_zone: tuple = (0.25, 0.78, 1.12, 0.5)    # feet sit at the bottom edge and often just below the box
    # A worker touching the bottom of the photo is only "torso cut off" if their box is short for its width:
    # someone cut off at the knees (tall box) still shows a full torso, so their vest can be judged.
    torso_min_aspect: float = 1.8
    # Goggles and gloves are tiny details: below this height the worker is too small to judge them.
    detail_min_height_px: int = 120
    detail_min_height_frac: float = 0.18

    # A helmet or vest seen below its class confidence but above this floor is "weak evidence":
    # it never counts as worn, but it stops us from accusing the worker (they go to NEEDS_REVIEW).
    weak_conf_floor: float = 0.15

    # A standing, sitting or bending person is never much wider than tall. A "person" box wider than this
    # (width / height) is a machine, a pile or a merged blob, so it is ignored instead of being judged.
    person_max_aspect: float = 2.0

    # A bare or covered head (no helmet) seen in the head zone. If it is more convincing than a helmet on the same
    # head, the "helmet" was really a cap, beanie or head cloth. Needs a model trained with a `head` class.
    head_conf: float = 0.35

    # "Worker down" (fall, collapse, struck down). In a photo, a person box far wider than tall is only flagged for a
    # check. In video, a person who goes from upright to lying within `fall_drop_window_s` and stays still for
    # `fall_still_s` raises an alert; someone already lying when first seen needs `lying_still_s` of stillness.
    down_min_conf: float = 0.5
    down_max_aspect: float = 6.0
    fall_upright_aspect: float = 0.9
    fall_down_aspect: float = 1.2
    fall_drop_window_s: float = 1.5
    fall_still_s: float = 3.0
    lying_aspect: float = 1.8
    lying_still_s: float = 5.0
    fall_move_frac: float = 0.35

    # Which equipment every worker must wear.
    required: tuple[str, ...] = ("helmet", "vest")

    # Body zones, as fractions of the person box height. The head zone starts a little above the
    # box because helmets often poke out of it; the torso zone skips the neck and the legs.
    head_zone_frac: float = 0.35
    head_top_margin: float = 0.10
    # A helmet must also sit in the middle of the box sideways. A worker whose box is oversized (it swallows a
    # neighbour) would otherwise be credited with the neighbour's helmet at the edge of their box.
    head_x_margin: float = 0.15
    torso_top: float = 0.20
    torso_bottom: float = 0.75  # seated and bending workers have a lower torso, relative to their box, than standing ones

    # How much of an item must sit in its zone / on the person before it counts as worn.
    helmet_min_in_zone: float = 0.50
    vest_min_in_person: float = 0.60
    # Size checks so a small patch, or a vest held up or draped, is not taken as worn.
    vest_min_width_ratio: float = 0.45
    vest_min_height_ratio: float = 0.20

    # Weak-evidence flags. A flagged worker with a missing item becomes NEEDS_REVIEW, not a violation.
    tiny_min_height_px: int = 80
    tiny_min_height_frac: float = 0.08
    edge_margin_frac: float = 0.02
    low_person_conf: float = 0.45
    crowded_iou: float = 0.30
    wide_box_ratio: float = 1.35  # seated and bending workers are wider than tall; beyond this it is likely several people merged

    # Tiled detection for small, far-away workers: the photo is also cut into tile_grid x tile_grid
    # overlapping pieces, each zoomed in and checked again. 0 turns it off (faster, misses background workers).
    backlit_review: bool = True  # a worker who is a dark silhouette against a bright background becomes "needs review", not "violation"
    tile_grid: int = 2
    tile_overlap: float = 0.25
    # A person seen only in a zoomed tile must be more convincing, because a false person is a false violation.
    tile_person_conf: float = 0.55

    # Low-light handling (CLAHE contrast enhancement) and inference size.
    dark_mean_threshold: int = 70
    clahe_clip: float = 2.0
    clahe_grid: int = 8
    imgsz: int = 960

    # Video: a violation is confirmed if seen in `persist_min` of the last `persist_window` usable frames.
    persist_window: int = 8
    persist_min: int = 5
