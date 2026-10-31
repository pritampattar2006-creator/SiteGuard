"""Low-light handling: brighten dark photos before detection."""
from __future__ import annotations

import cv2

from .config import Config


def is_dark(image_bgr, cfg: Config) -> bool:
    return float(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).mean()) < cfg.dark_mean_threshold


def apply_clahe(image_bgr, cfg: Config):
    """Boost local contrast on the lightness channel only, so colours (vest orange) stay true."""
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=cfg.clahe_clip, tileGridSize=(cfg.clahe_grid, cfg.clahe_grid))
    return cv2.cvtColor(cv2.merge((clahe.apply(l), a, b)), cv2.COLOR_LAB2BGR)


def maybe_enhance(image_bgr, cfg: Config, mode: str = "auto"):
    """mode: "auto" (only dark images), "on" (always) or "off". Returns (image, was_enhanced)."""
    if mode == "off" or (mode == "auto" and not is_dark(image_bgr, cfg)):
        return image_bgr, False
    return apply_clahe(image_bgr, cfg), True
