"""Draw per-worker verdicts on an image."""
from __future__ import annotations

import cv2

from .types import COMPLIANT, NEEDS_REVIEW, VIOLATION, AnalysisResult, Detection, Verdict

# BGR colours
GREEN = (60, 180, 75)
RED = (50, 50, 230)
AMBER = (0, 170, 255)
BLUE = (230, 160, 40)
GREY = (150, 150, 150)
NAVY = (43, 32, 18)
PURPLE = (170, 40, 150)

STATUS_COLOUR = {COMPLIANT: GREEN, NEEDS_REVIEW: AMBER}  # anything else is a violation -> RED


def label_text(verdict: Verdict, prefix: str = "Worker") -> str:
    if verdict.status == COMPLIANT:
        return f"{prefix} {verdict.worker_id}: OK"
    if verdict.status == NEEDS_REVIEW:
        return f"{prefix} {verdict.worker_id}: REVIEW"
    return f"{prefix} {verdict.worker_id}: " + " + ".join(verdict.missing)


def _box(image, det: Detection, colour, thickness: int) -> None:
    x1, y1, x2, y2 = det.box
    cv2.rectangle(image, (x1, y1), (x2, y2), colour, thickness)


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _label(image, text: str, x: int, y: int, colour, font: float, thickness: int, placed: list) -> None:
    """Text on a filled background so it stays readable on any photo.

    In crowds, neighbouring workers have almost the same top edge, so a label that would land on
    one already drawn is stepped upwards until it is free (or until it runs off the image).
    """
    (w, h), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font, thickness)
    box_h = h + base + 4
    top = max(y - box_h, 0)
    rect = (x, top, x + w + 6, top + box_h)
    while any(_overlaps(rect, other) for other in placed) and rect[1] - box_h >= 0:
        rect = (rect[0], rect[1] - box_h, rect[2], rect[3] - box_h)
    placed.append(rect)
    cv2.rectangle(image, (rect[0], rect[1]), (rect[2], rect[3]), colour, -1)
    cv2.putText(image, text, (rect[0] + 3, rect[1] + h + 1), cv2.FONT_HERSHEY_SIMPLEX, font, (255, 255, 255), thickness, cv2.LINE_AA)


def _item_tag(image, det: Detection, font: float, thickness: int) -> None:
    """A small name tag inside an equipment box, e.g. 'vest 0.82', so it is clear what was matched. Skipped on tiny boxes."""
    x1, y1, x2, y2 = det.box
    if x2 - x1 < 70 * font / 0.6 * 0.7:
        return
    text = f"{det.label} {det.conf:.2f}"
    (w, h), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font * 0.8, thickness)
    cv2.rectangle(image, (x1, y2 - h - base - 3), (x1 + w + 6, y2), BLUE, -1)
    cv2.putText(image, text, (x1 + 3, y2 - base), cv2.FONT_HERSHEY_SIMPLEX, font * 0.8, (255, 255, 255), thickness, cv2.LINE_AA)


def _banner(image, result: AnalysisResult, font: float, thickness: int) -> None:
    """A strip across the top: how many workers, and how many are OK / violations / need review."""
    ok = sum(v.status == COMPLIANT for v in result.verdicts)
    bad = sum(v.status == VIOLATION for v in result.verdicts)
    review = sum(v.status == NEEDS_REVIEW for v in result.verdicts)
    parts = [(f"{len(result.verdicts)} workers", (255, 255, 255)), (f"{ok} OK", GREEN), (f"{bad} violation", RED), (f"{review} review", AMBER)]
    if result.down_candidates:
        parts.append((f"{len(result.down_candidates)} possible person down", PURPLE))
    if result.objects:
        parts.append((f"{len(result.objects)} object, not a worker", GREY))
    bar_h = int(34 * font / 0.6)
    overlay = image.copy()
    cv2.rectangle(overlay, (0, 0), (image.shape[1], bar_h), NAVY, -1)
    cv2.addWeighted(overlay, 0.86, image, 0.14, 0, image)
    x = 12
    for text, colour in parts:
        cv2.putText(image, text, (x, int(bar_h * 0.7)), cv2.FONT_HERSHEY_SIMPLEX, font * 1.05, colour, thickness + 1, cv2.LINE_AA)
        x += cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font * 1.05, thickness + 1)[0][0] + 28


def draw(image_bgr, result: AnalysisResult, show_unassigned: bool = True, prefix: str = "Worker"):
    """Return an annotated copy. Line width and text size scale with the image.

    Only people are boxed and labelled. Helmets and vests nobody is wearing are drawn (grey) only when
    `show_unassigned` is on, because they are objects, not workers.
    """
    out = image_bgr.copy()
    scale = max(out.shape[:2]) / 1000
    line = max(1, round(2 * scale))
    font = max(0.4, 0.6 * scale)
    text_w = max(1, round(scale))
    placed: list = []

    for match, verdict in zip(result.matches, result.verdicts):
        colour = STATUS_COLOUR.get(verdict.status, RED)
        for item in (match.helmet, match.vest, *[d for found in match.extras.values() for d in found]):
            if item is not None:
                _box(out, item, BLUE, line)
        _box(out, match.person, colour, line + 1)
    for match, verdict in zip(result.matches, result.verdicts):
        for item in (match.helmet, match.vest, *[d for found in match.extras.values() for d in found]):
            if item is not None:
                _item_tag(out, item, font, text_w)
    for match, verdict in zip(result.matches, result.verdicts):
        _label(out, label_text(verdict, prefix), match.person.box[0], match.person.box[1], STATUS_COLOUR.get(verdict.status, RED), font, text_w, placed)
    for det in result.down_candidates:  # someone possibly on the ground: purple, so it cannot be missed
        _box(out, det, PURPLE, line + 2)
        _label(out, "CHECK: PERSON ON GROUND?", det.box[0], det.box[1], PURPLE, font, text_w, placed)
    for det in result.unassigned if show_unassigned else []:
        _box(out, det, GREY, max(1, line - 1))
        _label(out, f"unassigned {det.label}", det.box[0], det.box[1], GREY, font * 0.9, text_w, placed)
    for det in result.objects:  # looked like a person to the main model, but a second check found no body: not a worker
        _box(out, det, GREY, max(1, line - 1))
        _label(out, "OBJECT: not a worker", det.box[0], det.box[1], GREY, font * 0.9, text_w, placed)
    if result.verdicts or result.down_candidates or result.objects:
        _banner(out, result, font, text_w)
    return out


def crop_person(image, box, margin: float = 0.25, min_width: int = 320):
    """The one worker (plus a margin) cut out of a picture, enlarged if small, so a case shows who it is about."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = [int(v) for v in box]
    mx, my = int((x2 - x1) * margin), int((y2 - y1) * margin)
    crop = image[max(0, y1 - my):min(h, y2 + my), max(0, x1 - mx):min(w, x2 + mx)]
    if crop.size and crop.shape[1] < min_width:
        scale = min_width / crop.shape[1]
        crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return crop


def draw_name(image, box, text: str) -> None:
    """A name tag under a person's box (used for a face-match suggestion)."""
    x1, y1, x2, y2 = box
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    top = max(0, min(image.shape[0] - h - 8, y2 + 2))
    cv2.rectangle(image, (x1, top), (x1 + w + 8, top + h + 8), (43, 32, 18), -1)
    cv2.putText(image, text, (x1 + 4, top + h + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
