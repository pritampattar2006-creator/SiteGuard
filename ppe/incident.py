"""Worker-down detection for video: a person who falls or collapses and does not get up.

What this can and cannot do. It watches each tracked person's box. A standing worker's box is taller than wide; a person
lying on the ground has a box much wider than tall. An alert is raised when a person
  * goes from upright to lying within a second or two and stays still (kind FALL), or
  * is already lying when first seen and stays still for longer (kind DOWN).
It cannot see *why* someone is down, so it cannot tell a heart attack from a fall or a blow from a falling object, and a
worker lying down to work under a machine can trigger it. Treat an alert as "someone should check now", not a diagnosis.
Pure Python, no model: it works on person boxes with track ids.
"""
from __future__ import annotations

from .config import Config
from .geometry import center, height, width
from .types import Detection


class FallMonitor:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._tracks: dict[int, dict] = {}

    def update(self, t: float, persons: list[Detection]) -> list[dict]:
        """Feed one analysed frame (time in seconds). Returns new alerts: dicts with time_s, worker_id, kind, reason."""
        cfg, alerts = self.cfg, []
        for person in persons:
            if person.track_id is None or person.conf < cfg.person_conf or height(person.box) <= 0:
                continue
            w, h = width(person.box), height(person.box)
            aspect = w / h
            cx, cy = center(person.box)
            st = self._tracks.setdefault(person.track_id, {"upright": None, "since": None, "anchor": None, "alerted": False, "sudden": False})

            if aspect <= cfg.fall_upright_aspect:  # standing or walking: reset
                st.update(upright=t, since=None, anchor=None, alerted=False, sudden=False)
                continue
            if aspect < cfg.fall_down_aspect:  # bending or crouching: neither up nor down, forget any stillness clock
                st.update(since=None, anchor=None)
                continue

            if st["since"] is None:  # just went down
                st.update(since=t, anchor=(cx, cy), sudden=st["upright"] is not None and t - st["upright"] <= cfg.fall_drop_window_s)
            ax, ay = st["anchor"]
            if ((cx - ax) ** 2 + (cy - ay) ** 2) ** 0.5 > cfg.fall_move_frac * max(w, h):  # still moving: restart the clock
                st.update(since=t, anchor=(cx, cy))
                continue

            needed = cfg.fall_still_s if st["sudden"] else cfg.lying_still_s
            lying_enough = st["sudden"] or aspect >= cfg.lying_aspect
            if lying_enough and not st["alerted"] and t - st["since"] >= needed:
                st["alerted"] = True
                kind = "FALL" if st["sudden"] else "DOWN"
                reason = ("Went from upright to lying and has not moved" if kind == "FALL" else "Lying on the ground and not moving") + f" for {t - st['since']:.0f} s."
                alerts.append({"time_s": round(t, 2), "worker_id": person.track_id, "kind": kind, "reason": reason})
        return alerts
