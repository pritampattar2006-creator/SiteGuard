"""Numbers and short sentences that turn the register into something a supervisor can act on. Pure Python."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

COUNTED = ("Open", "Disputed", "Acknowledged", "Resolved")  # a dismissed case was a mistake, so it never counts against anyone


def _day(record) -> date:
    return datetime.fromisoformat(record["occurred_at"]).date()


def counted(records) -> list:
    return [r for r in records if r["status"] in COUNTED]


def safety_score(records, today: date | None = None) -> int:
    """100 minus 8 for each violation in the last 30 days, minus 4 more for each still unanswered. Never below 0.

    Deliberately simple so a worker can see exactly how to raise it.
    """
    today = today or date.today()
    recent = [r for r in counted(records) if 0 <= (today - _day(r)).days < 30]
    penalty = 8 * len(recent) + 4 * sum(r["status"] == "Open" for r in recent)
    return max(0, 100 - penalty)


def score_label(score: int) -> tuple[str, str]:
    """(word, colour) for a safety score."""
    if score >= 90:
        return "Excellent", "#1f8a5b"
    if score >= 75:
        return "Good", "#4c9a2a"
    if score >= 50:
        return "Needs attention", "#d98a00"
    return "At risk", "#d1332e"


def days_since_last(records, today: date | None = None) -> int | None:
    today = today or date.today()
    days = [(today - _day(r)).days for r in counted(records)]
    return min(days) if days else None


def badges(records, today: date | None = None) -> list[tuple[str, str]]:
    """Recognition a worker has earned: (title, why)."""
    since = days_since_last(records, today)
    earned = []
    if not counted(records):
        earned.append(("Clean record", "No violations on record"))
    elif since is not None and since >= 30:
        earned.append(("30 days clean", "A month without a violation"))
    elif since is not None and since >= 7:
        earned.append(("7 days clean", "A week without a violation"))
    if records and not any(r["status"] in ("Open", "Disputed") for r in records):
        earned.append(("All cases closed", "Nothing is waiting for an answer"))
    return earned


def activity_calendar(records, weeks: int = 12, today: date | None = None) -> list[list[tuple[date, int]]]:
    """Columns of 7 days (Monday first), oldest week first, each day with its violation count."""
    today = today or date.today()
    per_day = Counter(_day(r) for r in counted(records))
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    return [[(start + timedelta(weeks=w, days=d), per_day.get(start + timedelta(weeks=w, days=d), 0)) for d in range(7)] for w in range(weeks)]


def daily_series(records, days: int = 7, today: date | None = None) -> list[int]:
    """Violations per day for the last `days` days, oldest first (for a small trend line)."""
    today = today or date.today()
    per_day = Counter(_day(r) for r in counted(records))
    return [per_day.get(today - timedelta(days=days - 1 - i), 0) for i in range(days)]


def hourly_counts(records) -> dict[int, int]:
    counts = Counter(datetime.fromisoformat(r["occurred_at"]).hour for r in counted(records))
    return {hour: counts.get(hour, 0) for hour in range(24)}


def weekday_hour(records) -> list[tuple[int, int, int]]:
    """(weekday 0=Mon, hour, count) for every non-empty cell of the weekday-by-hour grid."""
    cells = Counter((datetime.fromisoformat(r["occurred_at"]).weekday(), datetime.fromisoformat(r["occurred_at"]).hour) for r in counted(records))
    return [(wd, hr, n) for (wd, hr), n in sorted(cells.items())]


def repeat_offenders(records, minimum: int = 2) -> list[tuple[str, int]]:
    """Named workers with at least `minimum` counted violations, most first."""
    per_worker = Counter(r["worker_name"] for r in counted(records) if r["worker_name"])
    return [(name, n) for name, n in per_worker.most_common() if n >= minimum]


def risk_level(count: int, open_cases: int) -> tuple[str, str]:
    if count >= 3 or open_cases >= 2:
        return "High", "#d1332e"
    if count >= 2 or open_cases == 1:
        return "Watch", "#d98a00"
    return "Low", "#1f8a5b"


def sentences(records) -> list[str]:
    """Plain-English observations about the records, for the top of the analytics tab."""
    rows = counted(records)
    if not rows:
        return ["No violations recorded yet, so there is nothing to analyse."]
    out = []
    hours = Counter(datetime.fromisoformat(r["occurred_at"]).hour for r in rows)
    peak = max(hours, key=hours.get)
    out.append(f"Most violations happen around {peak:02d}:00 to {(peak + 1) % 24:02d}:00 ({hours[peak]} of {len(rows)}).")
    items = Counter(i.strip() for r in rows for i in r["missing"].split(",") if i.strip())
    top, n = items.most_common(1)[0]
    out.append(f"The most common violation is {top.lower()} ({n} time{'s' if n != 1 else ''}).")
    places = Counter(r["location"] for r in rows if r["location"])
    if places:
        place, n = places.most_common(1)[0]
        out.append(f"{place} has the most cases ({n}).")
    repeats = repeat_offenders(rows)
    if repeats:
        out.append(f"{len(repeats)} worker{'s have' if len(repeats) != 1 else ' has'} more than one violation: {', '.join(n for n, _ in repeats[:3])}.")
    waiting = sum(r["status"] in ("Open", "Disputed") for r in rows)
    if waiting:
        out.append(f"{waiting} case{'s are' if waiting != 1 else ' is'} still waiting for an answer or a decision.")
    return out


SAFETY_TIPS = {
    "NO HELMET": "A hard hat protects against falling objects and bumps. Wear it, with the chin strap fastened, wherever overhead work is going on.",
    "NO VEST": "A high-visibility vest lets machine operators and drivers see you in time. Keep it on and fastened, and replace it when the strips fade.",
    "NO GOGGLES": "Safety goggles protect your eyes from dust, chips and splashes. Wear them whenever you cut, grind, drill or pour.",
    "NO GLOVES": "Gloves protect your hands from cuts, burns and chemicals. Choose the type that matches the task.",
    "NO BOOTS": "Safety boots protect against dropped objects, nails and slips. Closed, sturdy footwear is required on site.",
}


def tips_for(missing: list[str]) -> list[str]:
    return [SAFETY_TIPS[m] for m in dict.fromkeys(missing) if m in SAFETY_TIPS]
