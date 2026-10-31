"""Saving a small data file safely on Windows.

The usual way to save without ever leaving a half-written file is to write a temporary file and swap it in with os.replace. On Windows that swap is
refused ("Access is denied") whenever another program has the target open for a moment (the web service reading it, a virus scanner, a file indexer).
That once stopped a whole video from being processed, so the swap is retried a few times and, if it still cannot be done, the data is written straight
into the file instead of being lost.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


def write_text_safely(path: Path, text: str, tries: int = 8, wait_s: float = 0.05) -> None:
    path = Path(path)
    temp = path.with_suffix(".tmp")
    temp.write_text(text, encoding="utf-8")
    for attempt in range(tries):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            time.sleep(wait_s * (attempt + 1))
    path.write_text(text, encoding="utf-8")  # the swap was refused every time: write in place rather than lose the data
    try:
        temp.unlink()
    except OSError:
        pass
