"""Score the system on our own hard-case photos.

Inputs
  eval/test_images/*.jpg|png   photos that were NOT used for training
  eval/ground_truth.csv        one row per worker, written by looking at each photo, left to right:
      image,group,worker,expected_status,expected_missing,expected_unassigned_helmets
      mixed_01.jpg,mixed,2,VIOLATION,helmet,0
      table_01.jpg,helmet_on_table,1,VIOLATION,helmet,1
  expected_status is COMPLIANT, VIOLATION or NEEDS_REVIEW; expected_missing is "helmet;vest" or empty.

Usage:  python eval/run_eval.py --weights weights/best.pt [--enhance auto|on|off]
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from ppe.types import VIOLATION, AnalysisResult


@dataclass
class Truth:
    group: str
    workers: list[tuple[str, frozenset[str]]] = field(default_factory=list)  # (status, missing) left to right
    unassigned_helmets: int | None = None


@dataclass
class WorkerRow:
    image: str
    group: str
    worker: int
    expected: str
    predicted: str
    correct: bool
    reason: str


def load_ground_truth(path: Path) -> dict[str, Truth]:
    truth: dict[str, Truth] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entry = truth.setdefault(row["image"], Truth(group=row["group"]))
            missing = frozenset(m.strip() for m in row["expected_missing"].split(";") if m.strip())
            entry.workers.append((row["expected_status"].strip().upper(), missing))
            if row.get("expected_unassigned_helmets", "").strip():
                entry.unassigned_helmets = int(row["expected_unassigned_helmets"])
    return truth


def _describe(status: str, missing) -> str:
    return f"{status} ({', '.join(sorted(missing))})" if missing else status


def compare(image: str, truth: Truth, result: AnalysisResult) -> tuple[list[WorkerRow], list[str]]:
    """Return one row per expected worker, plus image-level problems (worker count, unassigned helmets)."""
    problems: list[str] = []
    rows: list[WorkerRow] = []
    expected, found = len(truth.workers), len(result.verdicts)

    if expected != found:
        problems.append(f"expected {expected} workers, detected {found}")
        for i, (status, missing) in enumerate(truth.workers, 1):
            rows.append(WorkerRow(image, truth.group, i, _describe(status, missing), f"worker count mismatch ({found} detected)", False, ""))
        return rows, problems

    for i, ((status, missing), verdict) in enumerate(zip(truth.workers, result.verdicts), 1):
        predicted_missing = frozenset(m.removeprefix("NO ").lower() for m in verdict.missing)
        # Missing items only matter when the verdict is a violation.
        same = verdict.status == status and (status != VIOLATION or predicted_missing == missing)
        rows.append(
            WorkerRow(
                image, truth.group, i,
                _describe(status, missing),
                _describe(verdict.status, predicted_missing if verdict.status == VIOLATION else frozenset()),
                same, verdict.reason,
            )
        )

    if truth.unassigned_helmets is not None:
        actual = sum(d.label == "helmet" for d in result.unassigned)
        if actual != truth.unassigned_helmets:
            problems.append(f"expected {truth.unassigned_helmets} unassigned helmet(s), got {actual}")
    return rows, problems


def by_group(rows: list[WorkerRow]) -> list[dict]:
    groups: dict[str, list[WorkerRow]] = defaultdict(list)
    for row in rows:
        groups[row.group].append(row)
    table = []
    for name, items in sorted(groups.items()):
        correct = sum(r.correct for r in items)
        table.append(
            {"group": name, "images": len({r.image for r in items}), "workers": len(items),
             "correct": correct, "accuracy": f"{100 * correct / len(items):.0f}%"}
        )
    return table


def to_markdown(table: list[dict]) -> str:
    lines = ["| Group | Images | Workers | Correct | Accuracy |", "|---|---|---|---|---|"]
    lines += [f"| {t['group']} | {t['images']} | {t['workers']} | {t['correct']} | {t['accuracy']} |" for t in table]
    total = sum(t["workers"] for t in table)
    right = sum(t["correct"] for t in table)
    lines.append(f"| **all** | {sum(t['images'] for t in table)} | {total} | {right} | {100 * right / total:.0f}% |" if total else "")
    return "\n".join(lines)


def main() -> None:
    import argparse
    from dataclasses import replace

    import cv2

    from ppe.config import Config
    from ppe.detector import Detector
    from ppe.pipeline import analyze

    here = Path(__file__).parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--weights", default="weights/best.pt")
    parser.add_argument("--enhance", default="auto", choices=["auto", "on", "off"])
    parser.add_argument("--images", default=str(here / "test_images"))
    parser.add_argument("--truth", default=str(here / "ground_truth.csv"))
    args = parser.parse_args()

    truth = load_ground_truth(Path(args.truth))
    if not truth:
        raise SystemExit(f"No rows in {args.truth}. Fill it in first (see the format at the top of this file).")

    detector, cfg = Detector(args.weights), Config()
    rows: list[WorkerRow] = []
    problems: list[tuple[str, str]] = []
    for name, expected in truth.items():
        image = cv2.imread(str(Path(args.images) / name))
        if image is None:
            raise SystemExit(f"Cannot read {Path(args.images) / name}. Never skip an image: fix the path or the file.")
        image_rows, image_problems = compare(name, expected, analyze(image, cfg, detector, args.enhance))
        rows += image_rows
        problems += [(name, p) for p in image_problems]

    table = by_group(rows)
    print(to_markdown(table))
    wrong = [r for r in rows if not r.correct]
    if wrong or problems:
        print("\nWrong or flagged:")
    for r in wrong:
        print(f"  {r.image} worker {r.worker}: expected {r.expected}, got {r.predicted}. {r.reason}")
    for name, p in problems:
        print(f"  {name}: {p}")

    with open(here / "results.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "group", "worker", "expected", "predicted", "correct", "reason"])
        writer.writerows([r.image, r.group, r.worker, r.expected, r.predicted, r.correct, r.reason] for r in rows)
    (here / "results.md").write_text(to_markdown(table) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
