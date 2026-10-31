"""Turn a worker's matched equipment into a verdict. Pure Python.

Three outcomes, not two: if a worker is too small, cut off or overlapped to judge fairly, we say
NEEDS_REVIEW instead of accusing them of a violation.
"""
from __future__ import annotations

from .config import Config
from .types import (
    COMPLIANT,
    ITEMS,
    MISSING,
    NEEDS_REVIEW,
    NOT_REQUIRED,
    PRESENT,
    UNVERIFIABLE,
    VIOLATION,
    Verdict,
    WorkerMatch,
)

# Flags that make any absent item impossible to judge.
BLOCKING_FLAGS = ("tiny", "low_conf", "wide_box", "crowded")

# Extra flag that blocks only the items on a body part that is cut off by the edge of the photo.
EDGE_FLAG = {"helmet": "edge_top", "goggles": "edge_top", "vest": "torso_cut", "boots": "edge_bottom"}

# Goggles and gloves are small details: a distant worker is too small to judge them.
DETAIL_ITEMS = ("goggles", "gloves")

# Why an item cannot be verified, in priority order.
CANNOT_VERIFY = {
    "tiny": "Person is very small in the image, so the {item} cannot be verified.",
    "small_detail": "Person is too small in the image to judge the {item}.",
    "low_conf": "The person detection is uncertain, so the {item} cannot be verified.",
    "wide_box": "The person box is unusually wide (possibly several people), so the {item} cannot be verified.",
    "crowded": "Person overlaps others heavily, so the {item} cannot be verified.",
    "edge_top": "The head is cut off at the top of the image, so the {item} cannot be verified.",
    "edge_bottom": "The lower body is cut off at the bottom of the image, so the {item} cannot be verified.",
    "torso_cut": "The body is cut off at the bottom of the image above the waist, so the {item} cannot be verified.",
}
WEAK = "A possible {item} was seen on this worker but with low confidence, so it needs review."

NOT_FOUND = {
    "helmet": "No helmet found in this worker's head zone.",
    "vest": "No vest found on this worker's torso.",
    "goggles": "No safety goggles found on this worker's face.",
    "gloves": "No gloves found on this worker's hands.",
    "boots": "No safety boots found on this worker's feet.",
}


def _blocking_flag(item: str, flags: list[str]) -> str:
    """The first flag that stops this item being judged, or '' if nothing does."""
    candidates = [f"weak_{item}", *BLOCKING_FLAGS]
    if item in DETAIL_ITEMS:
        candidates.append("small_detail")
    if item in EDGE_FLAG:
        candidates.append(EDGE_FLAG[item])
    return next((flag for flag in candidates if flag in flags), "")


def _item_state(item: str, match: WorkerMatch, cfg: Config) -> str:
    present = bool(match.items_of(item))
    if item not in cfg.required:
        return PRESENT if present else NOT_REQUIRED
    if present:
        return PRESENT
    if item == "helmet" and "bare_head" in match.flags:
        return MISSING  # a bare or covered head was seen: positive evidence, so crowding or size does not excuse it
    return UNVERIFIABLE if _blocking_flag(item, match.flags) else MISSING


def _cannot_verify(item: str, flag: str) -> str:
    return WEAK.format(item=item) if flag.startswith("weak_") else CANNOT_VERIFY[flag].format(item=item)


def evaluate(match: WorkerMatch, cfg: Config) -> Verdict:
    states = {item: _item_state(item, match, cfg) for item in ITEMS}
    required = [item for item in ITEMS if item in cfg.required]
    required_states = [states[item] for item in required]

    if MISSING in required_states:
        status = VIOLATION
    elif UNVERIFIABLE in required_states:
        status = NEEDS_REVIEW
    else:
        status = COMPLIANT

    missing = [f"NO {item.upper()}" for item in required if states[item] == MISSING]

    sentences = [NOT_FOUND[item] for item in required if states[item] == MISSING]
    sentences += [_cannot_verify(item, _blocking_flag(item, match.flags)) for item in required if states[item] == UNVERIFIABLE]
    if status == COMPLIANT:
        sentences = [f"Required equipment found on this worker ({' and '.join(required)})."]

    return Verdict(
        worker_id=match.worker_id,
        status=status,
        helmet_state=states["helmet"],
        vest_state=states["vest"],
        missing=missing,
        reason=" ".join(sentences),
        states=states,
    )


def evaluate_all(matches: list[WorkerMatch], cfg: Config) -> list[Verdict]:
    return [evaluate(m, cfg) for m in matches]
