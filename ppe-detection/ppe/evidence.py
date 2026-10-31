"""Save the evidence images for a violation: the annotated photo and a close-up of the worker."""
from __future__ import annotations

from pathlib import Path

import cv2

from .types import Box

EVIDENCE_DIR = Path("outputs/evidence")


def crop_worker(image_bgr, box: Box, margin: float = 0.12):
    """Close-up of one worker with a little room around them."""
    h, w = image_bgr.shape[:2]
    x1, y1, x2, y2 = box
    mx, my = int((x2 - x1) * margin), int((y2 - y1) * margin)
    return image_bgr[max(y1 - my, 0) : min(y2 + my, h), max(x1 - mx, 0) : min(x2 + mx, w)]


def save_evidence(annotated_bgr, original_bgr, person_box: Box, stem: str, folder: Path | None = None) -> tuple[str, str]:
    """Write `<stem>.jpg` (full annotated photo) and `<stem>_crop.jpg` (worker close-up). Returns both paths."""
    folder = Path(folder or EVIDENCE_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    full, close = folder / f"{stem}.jpg", folder / f"{stem}_crop.jpg"
    cv2.imwrite(str(full), annotated_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    cv2.imwrite(str(close), crop_worker(original_bgr, person_box), [cv2.IMWRITE_JPEG_QUALITY, 90])
    return str(full), str(close)
