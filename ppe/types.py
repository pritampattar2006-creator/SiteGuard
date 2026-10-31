"""Plain data contracts. These objects are the only thing the modules pass to each other."""
from __future__ import annotations

from dataclasses import dataclass, field

Box = tuple[int, int, int, int]  # (x1, y1, x2, y2) in pixels

# Verdict status
COMPLIANT = "COMPLIANT"
VIOLATION = "VIOLATION"
NEEDS_REVIEW = "NEEDS_REVIEW"

# Per-item state
PRESENT = "PRESENT"
MISSING = "MISSING"
UNVERIFIABLE = "UNVERIFIABLE"
NOT_REQUIRED = "NOT_REQUIRED"


@dataclass(frozen=True)
class Detection:
    label: str  # "person", "helmet" or "vest"
    conf: float
    box: Box
    track_id: int | None = None


# Every kind of equipment the system can check, in the order shown on screen.
ITEMS = ("helmet", "vest", "goggles", "gloves", "boots")
ITEM_NAMES = {"helmet": "Helmet", "vest": "Vest", "goggles": "Goggles", "gloves": "Gloves", "boots": "Boots"}


@dataclass
class WorkerMatch:
    """One person and the equipment geometrically assigned to them."""

    worker_id: int
    person: Detection
    helmet: Detection | None
    vest: Detection | None
    flags: list[str] = field(default_factory=list)  # reasons the evidence may be weak
    extras: dict[str, list[Detection]] = field(default_factory=dict)  # goggles / gloves / boots (a worker may wear several)

    def items_of(self, item: str) -> list[Detection]:
        """Everything matched to this worker for one kind of equipment."""
        if item == "helmet":
            return [self.helmet] if self.helmet else []
        if item == "vest":
            return [self.vest] if self.vest else []
        return self.extras.get(item, [])


@dataclass
class Verdict:
    worker_id: int
    status: str  # COMPLIANT, VIOLATION or NEEDS_REVIEW
    helmet_state: str
    vest_state: str
    missing: list[str]  # display names, e.g. ["NO HELMET"]
    reason: str
    states: dict[str, str] = field(default_factory=dict)  # state of every item, including goggles / gloves / boots


@dataclass
class AnalysisResult:
    verdicts: list[Verdict]
    matches: list[WorkerMatch]
    unassigned: list[Detection]  # helmets / vests that nobody is wearing
    enhanced: bool
    image_size: tuple[int, int]  # (width, height)
    people: list[Detection] = field(default_factory=list)  # every confident person box, including lying ones (for fall checks)
    down_candidates: list[Detection] = field(default_factory=list)  # person boxes far wider than tall: possibly someone on the ground
    objects: list[Detection] = field(default_factory=list)  # "person" boxes a second check found to be objects (never judged for PPE)
