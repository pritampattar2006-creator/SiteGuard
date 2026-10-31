"""Thin wrapper around Ultralytics YOLO models that returns our own Detection type.

The main model finds person / helmet / vest. An optional second model (trained on six classes) does two jobs:
it finds the small extras (gloves, boots, goggles), and in ensemble mode it gives a second opinion on person /
helmet / vest, so a vest or helmet that one model hesitates over is judged with more evidence.
"""
from __future__ import annotations

from .config import Config
from .geometry import clip_box
from .types import Detection

# Dataset class names differ between sources, so classes are matched by name, never by index.
# Anything not listed ("no_helmet", "none", ...) is ignored on purpose: a missing item is decided per
# worker in associate.py from the *absence* of a positive detection.
ALIASES = {
    "person": "person",
    "worker": "person",
    "helmet": "helmet",
    "hardhat": "helmet",
    "safetyhelmet": "helmet",
    "vest": "vest",
    "safetyvest": "vest",
    "hivisvest": "vest",
    "reflectivevest": "vest",
    "head": "head",  # a bare or covered head with no helmet (needs a model trained with this class)
    "nohelmet": "head",
    "gloves": "gloves",
    "glove": "gloves",
    "boots": "boots",
    "boot": "boots",
    "safetyshoes": "boots",
    "goggles": "goggles",
    "goggle": "goggles",
    "glasses": "goggles",
    "safetyglasses": "goggles",
}
EXTRA_LABELS = ("gloves", "boots", "goggles")
CORE_LABELS = ("person", "helmet", "vest")


def _key(name: str) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def tile_origins(width: int, height: int, grid: int, overlap: float) -> list[tuple[int, int, int, int]]:
    """Overlapping tiles as (x0, y0, w, h). Neighbouring tiles share `overlap` of their size."""
    tile_w, tile_h = min(width, int(width / grid * (1 + overlap))), min(height, int(height / grid * (1 + overlap)))
    tiles = []
    for gy in range(grid):
        for gx in range(grid):
            x0 = min(max(int(gx * width / grid - overlap * width / grid / 2), 0), width - tile_w)
            y0 = min(max(int(gy * height / grid - overlap * height / grid / 2), 0), height - tile_h)
            tiles.append((x0, y0, tile_w, tile_h))
    return tiles


def cut_by_tile_edge(box, tile: tuple[int, int, int, int], image_w: int, image_h: int, margin: int = 3) -> bool:
    """True if `box` (tile coordinates) touches a tile edge that is not also the image edge.

    Such a box is a person or item sliced in half by the tile boundary. The neighbouring tile sees it whole.
    """
    x0, y0, w, h = tile
    return (
        (box[0] <= margin and x0 > 0)
        or (box[2] >= w - margin and x0 + w < image_w)
        or (box[1] <= margin and y0 > 0)
        or (box[3] >= h - margin and y0 + h < image_h)
    )


def merge_detections(detections: list[Detection], iou_limit: float = 0.5, inside_limit: float = 0.85) -> list[Detection]:
    """Class-by-class suppression of repeats: keep the most confident of overlapping same-class boxes.

    A box is also dropped when almost all of it lies inside a more confident box of its class. That
    is the half-box a tile boundary leaves on a person who is already detected whole.
    """
    from .geometry import fraction_inside, iou

    kept: list[Detection] = []
    for det in sorted(detections, key=lambda d: -d.conf):
        repeat = any(
            k.label == det.label and (iou(det.box, k.box) > iou_limit or fraction_inside(det.box, k.box) >= inside_limit)
            for k in kept
        )
        if not repeat:
            kept.append(det)
    return kept


def fuse_detections(a: list[Detection], b: list[Detection], iou_limit: float = 0.55) -> list[Detection]:
    """Combine two models' detections. Boxes both models agree on get the average box and confidence;
    a box only one model sees keeps half its confidence, so agreement counts for more than a lone guess."""
    from .geometry import iou

    fused: list[Detection] = []
    used: set[int] = set()
    for det in a:
        best, best_j = 0.0, None
        for j, other in enumerate(b):
            if j in used or other.label != det.label:
                continue
            overlap = iou(det.box, other.box)
            if overlap > best:
                best, best_j = overlap, j
        if best_j is not None and best >= iou_limit:
            other = b[best_j]
            used.add(best_j)
            box = tuple(int((p + q) / 2) for p, q in zip(det.box, other.box))
            fused.append(Detection(det.label, (det.conf + other.conf) / 2, box, det.track_id))
        else:
            fused.append(Detection(det.label, det.conf / 2, det.box, det.track_id))
    fused += [Detection(o.label, o.conf / 2, o.box, o.track_id) for j, o in enumerate(b) if j not in used]
    return fused


class Detector:
    def __init__(self, weights_path: str, device: str | None = None, extra_weights: str | None = None,
                 augment: bool = False, ensemble: bool = False, verify_people: bool = True, tracker: str = "bytetrack.yaml",
                 night_weights: str | None = None):
        from ultralytics import YOLO  # imported here so the core logic needs no ML install

        from .verify import PersonVerifier

        self.model = YOLO(weights_path)
        # A second copy of the model, trained on darkened photos too, used only when a picture is dark (best at not accusing people by mistake in the dark).
        self.night_model = YOLO(night_weights) if night_weights else None
        self.dark = False  # the pipeline sets this when it had to brighten the picture
        self._video_dark: bool | None = None  # a video keeps one model from start to finish, so track numbers do not restart
        self.device = device
        self.tracker = tracker  # "bytetrack.yaml", or a path such as config/botsort_reid.yaml (also uses appearance to keep people steady)
        self.verifier = PersonVerifier(device=device) if verify_people else None  # second opinion on every "person" box
        self.last_objects: list[Detection] = []
        self.augment = augment  # test-time augmentation: look at the photo flipped and rescaled too, then average
        self.ensemble = ensemble  # also use the second model's opinion on person / helmet / vest
        self.label_of = {i: ALIASES[_key(n)] for i, n in self.model.names.items() if _key(n) in ALIASES}
        missing = {"person", "helmet", "vest"} - set(self.label_of.values())
        if missing:
            raise ValueError(
                f"Model is missing class(es) {sorted(missing)}. Classes found: {list(self.model.names.values())}"
            )
        # The second model supplies the small extras, and (in ensemble mode) a second opinion on the big three.
        self.extra_model = YOLO(extra_weights) if extra_weights else None
        self.extra_label_of: dict[int, str] = {}
        self.second_label_of: dict[int, str] = {}
        if self.extra_model is not None:
            every = {i: ALIASES[_key(n)] for i, n in self.extra_model.names.items() if _key(n) in ALIASES}
            self.extra_label_of = {i: lab for i, lab in every.items() if lab in EXTRA_LABELS}
            self.second_label_of = {i: lab for i, lab in every.items() if lab in CORE_LABELS}
            if not self.extra_label_of:
                raise ValueError(f"Extra model has no gloves / boots / goggles class. Found: {list(self.extra_model.names.values())}")

    @property
    def available_items(self) -> list[str]:
        """Equipment this detector can actually check."""
        extras = sorted(set(self.extra_label_of.values()), key=["goggles", "gloves", "boots"].index)
        return ["helmet", "vest", *extras]

    @property
    def can_ensemble(self) -> bool:
        return self.extra_model is not None and {"person", "helmet", "vest"} <= set(self.second_label_of.values())

    def _extras(self, image_bgr, imgsz: int, conf: float, full_w: int, full_h: int) -> list[Detection]:
        if self.extra_model is None:
            return []
        return self._run(self.extra_model, self.extra_label_of, image_bgr, imgsz, conf, (0, 0), full_w, full_h)

    def reset_tracking(self) -> None:
        """Forget every tracked person (call before and after a video), so the next clip or photo starts clean."""
        self.model.predictor = None
        if self.night_model is not None:
            self.night_model.predictor = None
        self._video_dark = None
        if self.verifier is not None:
            self.verifier.reset()

    def _model_for(self, tracking: bool):
        dark = self.dark
        if tracking:
            if self._video_dark is None:
                self._video_dark = dark
            dark = self._video_dark
        return self.night_model if (dark and self.night_model is not None) else self.model

    def _screen(self, image_bgr, detections: list[Detection]) -> list[Detection]:
        """Drop "person" boxes that a second check found to be objects (kept in last_objects, so they can be shown)."""
        if self.verifier is None:
            self.last_objects = []
            return detections
        kept, self.last_objects = self.verifier.screen(image_bgr, detections)
        return kept

    def detect(self, image_bgr, cfg: Config) -> list[Detection]:
        return self._screen(image_bgr, self._detect_raw(image_bgr, cfg))

    def track(self, image_bgr, cfg: Config) -> list[Detection]:
        return self._screen(image_bgr, self._track_raw(image_bgr, cfg))

    def _track_raw(self, image_bgr, cfg: Config) -> list[Detection]:
        """Like _detect_raw(), but through Ultralytics' built-in ByteTrack so each person keeps an id across frames."""
        floor = min(cfg.weak_conf_floor, cfg.person_conf, cfg.helmet_conf, cfg.vest_conf)
        result = self._model_for(True).track(
            image_bgr, persist=True, tracker=self.tracker, imgsz=cfg.imgsz, conf=floor, device=self.device, verbose=False
        )[0]
        height, width = image_bgr.shape[:2]
        ids = result.boxes.id.tolist() if result.boxes.id is not None else [None] * len(result.boxes)

        detections = []
        for xyxy, cls, conf, track_id in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist(), ids):
            label = self.label_of.get(int(cls))
            if label is not None:
                keep_id = int(track_id) if label == "person" and track_id is not None else None
                detections.append(Detection(label, float(conf), clip_box(tuple(xyxy), width, height), keep_id))
        extras = self._extras(image_bgr, cfg.imgsz, cfg.weak_conf_floor, width, height) if self._needs_extras(cfg) else []
        return detections + extras

    @staticmethod
    def _needs_extras(cfg: Config) -> bool:
        """The second model is only worth running when the rule set asks for gloves, boots or goggles."""
        return any(item in cfg.required for item in EXTRA_LABELS)

    def _detect_with(self, model, label_of, image_bgr, cfg: Config) -> list[Detection]:
        """One model over the whole photo, plus zoomed tiles for small workers when enabled."""
        floor = min(cfg.weak_conf_floor, cfg.person_conf, cfg.helmet_conf, cfg.vest_conf)
        height, width = image_bgr.shape[:2]
        detections = self._run(model, label_of, image_bgr, cfg.imgsz, floor, (0, 0), width, height)
        if cfg.tile_grid > 0:
            for tile in tile_origins(width, height, cfg.tile_grid, cfg.tile_overlap):
                x0, y0, tile_w, tile_h = tile
                crop = image_bgr[y0 : y0 + tile_h, x0 : x0 + tile_w]
                found = self._run(model, label_of, crop, cfg.imgsz, floor, (x0, y0), width, height)
                detections += [
                    d for d in found
                    if not cut_by_tile_edge((d.box[0] - x0, d.box[1] - y0, d.box[2] - x0, d.box[3] - y0), tile, width, height)
                    and (d.label != "person" or d.conf >= cfg.tile_person_conf)
                ]
            detections = merge_detections(detections)
        return detections

    def _detect_raw(self, image_bgr, cfg: Config) -> list[Detection]:
        """Detect everything, keeping detections down to the weak-evidence floor.

        Per-class confidence thresholds are applied later, in associate(), because a detection just
        under its threshold is still useful there: it stops us accusing a worker (see Config.weak_conf_floor).
        """
        height, width = image_bgr.shape[:2]
        detections = self._detect_with(self._model_for(False), self.label_of, image_bgr, cfg)
        if self.ensemble and self.can_ensemble:
            second = self._detect_with(self.extra_model, self.second_label_of, image_bgr, cfg)
            detections = fuse_detections(detections, second)
        extras = self._extras(image_bgr, cfg.imgsz, cfg.weak_conf_floor, width, height) if self._needs_extras(cfg) else []
        return merge_detections(detections + extras) if extras else detections

    def _run(self, model, label_of, image_bgr, imgsz, conf, offset, full_w, full_h) -> list[Detection]:
        result = model.predict(image_bgr, imgsz=imgsz, conf=conf, device=self.device, verbose=False, augment=self.augment)[0]
        ox, oy = offset
        detections = []
        for xyxy, cls, score in zip(result.boxes.xyxy.tolist(), result.boxes.cls.tolist(), result.boxes.conf.tolist()):
            label = label_of.get(int(cls))
            if label is not None:
                box = (xyxy[0] + ox, xyxy[1] + oy, xyxy[2] + ox, xyxy[3] + oy)
                detections.append(Detection(label, float(score), clip_box(box, full_w, full_h)))
        return detections


if __name__ == "__main__":
    import argparse

    import cv2

    parser = argparse.ArgumentParser(description="Print the detections for one image.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--weights", default="weights/best.pt")
    parser.add_argument("--extras", default=None, help="second model for gloves / boots / goggles (and a second opinion)")
    parser.add_argument("--best", action="store_true", help="accuracy mode: ensemble + test-time augmentation")
    args = parser.parse_args()
    for det in Detector(args.weights, extra_weights=args.extras, augment=args.best, ensemble=args.best).detect(cv2.imread(args.image), Config()):
        print(det)
