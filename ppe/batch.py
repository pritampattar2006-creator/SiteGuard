"""Analyse every image in a folder and write a report. With --watch, keep going as new images arrive.

Usage:  python -m ppe.batch --folder inbox [--weights weights/best.pt] [--out outputs/batch] [--watch]
Writes in --out: <image>_annotated.png, workers.csv, summary.json and report.html.
"""
from __future__ import annotations

import argparse
import html
import json
import time
from pathlib import Path

import cv2
import pandas as pd

from .annotate import draw
from .config import Config
from .pipeline import analyze
from .summary import summarize, workers_table

IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def analyse_image(path: Path, out: Path, cfg: Config, detector, enhance: str):
    """Return (table, summary) for one image, or None if it cannot be read (yet)."""
    image = cv2.imread(str(path))
    if image is None:
        return None
    result = analyze(image, cfg, detector, enhance)
    cv2.imwrite(str(out / f"{path.stem}_annotated.png"), draw(image, result))
    table = workers_table(result)
    table.insert(0, "Image", path.name)
    return table, summarize(result)


def write_report(done: dict, out: Path) -> None:
    tables = [t for t, _ in done.values()]
    pd.concat(tables, ignore_index=True).to_csv(out / "workers.csv", index=False) if tables else None
    totals = {
        key: sum(s[key] for _, s in done.values())
        for key in ("total_workers", "compliant", "violations", "needs_review")
    }
    (out / "summary.json").write_text(
        json.dumps({"images": len(done), **totals, "per_image": {n: s for n, (_, s) in done.items()}}, indent=2),
        encoding="utf-8",
    )
    sections = []
    for name, (table, summary) in done.items():
        stem = Path(name).stem
        sections.append(
            f"<h2>{html.escape(name)}</h2>"
            f"<p>{summary['total_workers']} workers: {summary['compliant']} compliant, "
            f"{summary['violations']} violations, {summary['needs_review']} need review.</p>"
            f"<img src='{html.escape(stem)}_annotated.png' style='max-width:900px;width:100%'>"
            + (table.drop(columns="Image").to_html(index=False, border=1) if len(table) else "<p>No workers detected.</p>")
        )
    (out / "report.html").write_text(
        "<!doctype html><meta charset='utf-8'><title>PPE batch report</title>"
        "<body style='font-family:Segoe UI,Arial;margin:24px'><h1>PPE batch report</h1>"
        f"<p><b>{len(done)}</b> images &bull; <b>{totals['total_workers']}</b> workers &bull; "
        f"<b>{totals['compliant']}</b> compliant &bull; <b>{totals['violations']}</b> violations &bull; "
        f"<b>{totals['needs_review']}</b> need review</p>" + "".join(sections) + "</body>",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--weights", default="weights/best.pt")
    parser.add_argument("--out", default="outputs/batch")
    parser.add_argument("--enhance", default="auto", choices=["auto", "on", "off"])
    parser.add_argument("--watch", action="store_true", help="keep running and analyse new images as they appear")
    args = parser.parse_args()

    from .detector import Detector

    folder, out, cfg = Path(args.folder), Path(args.out), Config()
    out.mkdir(parents=True, exist_ok=True)
    detector = Detector(args.weights)
    done: dict = {}

    while True:
        fresh = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in IMAGE_TYPES and p.name not in done]
        for path in fresh:
            outcome = analyse_image(path, out, cfg, detector, args.enhance)
            if outcome is None:  # unreadable or still being copied; try again next round
                continue
            done[path.name] = outcome
            s = outcome[1]
            print(f"{path.name}: {s['total_workers']} workers, {s['compliant']} ok, {s['violations']} violations, {s['needs_review']} review", flush=True)
        if fresh and done:
            write_report(done, out)
            print(f"Report: {out / 'report.html'}", flush=True)
        if not args.watch:
            break
        time.sleep(2)


if __name__ == "__main__":
    main()
