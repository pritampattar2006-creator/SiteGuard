"""Glue only: image -> (enhance) -> detect -> associate -> verdicts."""
from __future__ import annotations

from .associate import associate, down_candidates
from .config import Config
from .enhance import maybe_enhance
from .lighting import apply_backlit
from .rules import evaluate_all
from .types import AnalysisResult


def analyze(image_bgr, cfg: Config, detector, enhance_mode: str = "auto") -> AnalysisResult:
    """`detector` is anything with .detect(image, cfg), so tests can pass a fake one."""
    image, enhanced = maybe_enhance(image_bgr, cfg, enhance_mode)
    if hasattr(detector, "dark"):
        detector.dark = enhanced  # tells the detector the picture was dark, so it can use its night-trained model
    height, width = image.shape[:2]
    detections = detector.detect(image, cfg)
    matches, unassigned = associate(detections, (width, height), cfg)
    verdicts = evaluate_all(matches, cfg)
    if getattr(cfg, "backlit_review", True):
        apply_backlit(image_bgr, matches, verdicts)  # a silhouette against a bright background cannot be judged
    return AnalysisResult(
        verdicts=verdicts,
        matches=matches,
        unassigned=unassigned,
        enhanced=enhanced,
        image_size=(width, height),
        people=[d for d in detections if d.label == "person" and d.conf >= cfg.person_conf],
        down_candidates=down_candidates(detections, cfg),
        objects=list(getattr(detector, "last_objects", [])),  # set by Detector's person check; test fakes have none
    )


if __name__ == "__main__":
    import argparse
    from dataclasses import replace

    import cv2

    from .annotate import draw
    from .detector import Detector
    from .summary import workers_table

    parser = argparse.ArgumentParser(description="Check one image and print a per-worker table.")
    parser.add_argument("--image", required=True)
    parser.add_argument("--weights", default="weights/best.pt")
    parser.add_argument("--require", default="helmet,vest")
    parser.add_argument("--enhance", default="auto", choices=["auto", "on", "off"])
    parser.add_argument("--save", help="write the annotated image here")
    args = parser.parse_args()

    config = replace(Config(), required=tuple(args.require.split(",")))
    picture = cv2.imread(args.image)
    outcome = analyze(picture, config, Detector(args.weights), args.enhance)
    print(workers_table(outcome).to_string(index=False) if outcome.verdicts else "No workers detected.")
    for item in outcome.unassigned:
        print(f"Not on any worker: {item.label}")
    if args.save:
        cv2.imwrite(args.save, draw(picture, outcome))
