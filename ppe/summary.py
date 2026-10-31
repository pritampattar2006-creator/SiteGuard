"""Per-worker table, violation summary and CSV / JSON export."""
from __future__ import annotations

import json
from collections import Counter

import pandas as pd

from .types import (
    COMPLIANT,
    ITEM_NAMES,
    ITEMS,
    MISSING,
    NEEDS_REVIEW,
    NOT_REQUIRED,
    PRESENT,
    VIOLATION,
    AnalysisResult,
    Verdict,
)

_CELL = {PRESENT: "Yes", MISSING: "No", NOT_REQUIRED: "n/a"}


def item_state(verdict: Verdict, item: str) -> str:
    """State of one item for one worker (works for verdicts that only carry helmet/vest fields)."""
    if item in verdict.states:
        return verdict.states[item]
    return {"helmet": verdict.helmet_state, "vest": verdict.vest_state}.get(item, NOT_REQUIRED)


def checked_items(result: AnalysisResult) -> list[str]:
    """The equipment this result actually checked (helmet and vest if there are no workers to tell us)."""
    used = [i for i in ITEMS if any(item_state(v, i) != NOT_REQUIRED for v in result.verdicts)]
    return used or ["helmet", "vest"]


def workers_table(result: AnalysisResult) -> pd.DataFrame:
    items = checked_items(result)
    rows = [
        {
            "Worker": v.worker_id,
            **{ITEM_NAMES[i]: _CELL.get(item_state(v, i), "Unverifiable") for i in items},
            "Status": v.status,
            "Missing": ", ".join(v.missing),
            "Reason": v.reason,
        }
        for v in result.verdicts
    ]
    return pd.DataFrame(rows, columns=["Worker", *[ITEM_NAMES[i] for i in items], "Status", "Missing", "Reason"])


def summarize(result: AnalysisResult) -> dict:
    statuses = Counter(v.status for v in result.verdicts)
    labels = [d.label for d in result.unassigned]
    return {
        "total_workers": len(result.verdicts),
        "compliant": statuses[COMPLIANT],
        "violations": statuses[VIOLATION],
        "needs_review": statuses[NEEDS_REVIEW],
        "by_type": dict(Counter(name for v in result.verdicts for name in v.missing)),
        "possible_down": len(result.down_candidates),
        "unassigned": {item: labels.count(item) for item in ITEMS if item in ("helmet", "vest") or item in labels},
    }


def to_csv_bytes(result: AnalysisResult) -> bytes:
    return workers_table(result).to_csv(index=False).encode("utf-8")


def to_json_bytes(result: AnalysisResult) -> bytes:
    payload = {"summary": summarize(result), "workers": workers_table(result).to_dict(orient="records")}
    return json.dumps(payload, indent=2).encode("utf-8")
