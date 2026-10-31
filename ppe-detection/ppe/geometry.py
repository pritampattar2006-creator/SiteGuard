"""Pure box math on (x1, y1, x2, y2) tuples. No model, no pixels."""
from __future__ import annotations

from .types import Box


def width(box: Box) -> float:
    return max(0, box[2] - box[0])


def height(box: Box) -> float:
    return max(0, box[3] - box[1])


def area(box: Box) -> float:
    return width(box) * height(box)


def center(box: Box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def intersection_area(a: Box, b: Box) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def iou(a: Box, b: Box) -> float:
    inter = intersection_area(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def fraction_inside(a: Box, b: Box) -> float:
    """Share of `a`'s own area that lies inside `b`. Answers "is this item mostly in that zone?"."""
    a_area = area(a)
    return intersection_area(a, b) / a_area if a_area > 0 else 0.0


def contains_point(box: Box, point: tuple[float, float]) -> bool:
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def clip_box(box: Box, image_w: int, image_h: int) -> Box:
    x1, y1, x2, y2 = box
    return (
        int(min(max(x1, 0), image_w)),
        int(min(max(y1, 0), image_h)),
        int(min(max(x2, 0), image_w)),
        int(min(max(y2, 0), image_h)),
    )
