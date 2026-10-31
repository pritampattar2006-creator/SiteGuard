"""Drop-folder phone-use test. Put photos or clips in phone_test/in; results appear in phone_test/out and every decision is written to logs/phone.log.

  python scripts/phone_watch.py

Photos: one box and one short label per person, red when a phone is seen, amber 'PHONE? CHECK' for a raised hand with no phone seen (only for people tall enough to judge; smaller ones are logged, not drawn).
Clips: looked at about 5 times a second; a box is drawn while the alert holds, and each alert is logged with its time.
Processed files move to phone_test/done. Nothing here sends anything to the supervisor.
"""
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ppe.phone import MIN_GUESS_HEIGHT, PhoneMonitor, draw_findings  # noqa: E402

LOG = ROOT / "logs" / "phone.log"
IN, OUT, DONE = ROOT / "phone_test" / "in", ROOT / "phone_test" / "out", ROOT / "phone_test" / "done"
PHOTOS, CLIPS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}, {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}


def log(line: str) -> None:
    text = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {line}"
    print(text, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(text + "\n")


def weights(name: str) -> str:
    return str(next(p for p in (ROOT / "weights" / name, ROOT / name) if p.exists()))


def do_photo(mon: PhoneMonitor, path: Path) -> None:
    image = cv2.imread(str(path))
    if image is None:
        return log(f"photo | {path.name} | UNREADABLE")
    started = time.time()
    found = mon.look(image)
    shown = [f for f in found if not f["needs_review"] or f["box"][3] - f["box"][1] >= MIN_GUESS_HEIGHT]
    cv2.imwrite(str(OUT / f"{path.stem}_phone.jpg"), draw_findings(image, found))
    log(f"photo | {path.name} | {image.shape[1]}x{image.shape[0]} | phones seen {len(found and found[0]['phones'])} | drawn {len(shown)} | not drawn {len(found) - len(shown)} | {time.time() - started:.2f}s")
    for f in found:
        log(f"   {f['kind']:<13} box={f['box']} | {f['reason']}")
    if not found:
        log("   no phone use found")


def do_clip(mon: PhoneMonitor, path: Path) -> None:
    cap = cv2.VideoCapture(str(path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    ok, first = cap.read()  # the real size of the frames: a clip held upright is taller than wide, whatever the file header says
    if not ok:
        return log(f"clip  | {path.name} | UNREADABLE")
    size = (first.shape[1], first.shape[0])
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    writer = cv2.VideoWriter(str(OUT / f"{path.stem}_phone.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    step, n, drawn, alerts, looks, seen = max(1, int(fps / 5)), 0, [], [], 0, {}
    started = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if n % step == 0:
            looks += 1
            for a in mon.update(n / fps, frame):
                alerts.append(a)
                log(f"   ALERT t={a['time_s']}s | {a['kind']} | person {a['worker_id']} | {'review' if a['needs_review'] else 'confirmed'} | {a['reason']}")
            for f in mon.latest.values():
                seen[f["kind"]] = seen.get(f["kind"], 0) + 1
            drawn = mon.active()
        writer.write(draw_findings(frame, drawn))
        n += 1
    writer.release()
    cap.release()
    log(f"clip  | {path.name} | {size[0]}x{size[1]} {fps:.0f}fps {n} frames, {looks} looks | frames with phone use {seen or 'none'} | alerts {len(alerts)} | {time.time() - started:.1f}s")


def main() -> None:
    for folder in (IN, OUT, DONE, LOG.parent):
        folder.mkdir(parents=True, exist_ok=True)
    log("starting: loading models")
    mon = PhoneMonitor(weights("yolo11n-pose.pt"), weights("yolo11s.pt"), device=0)
    blank = cv2.imread(str(ROOT / "eval" / "cases" / "case_09.jpeg"))
    for _ in range(2):
        mon.look(blank)  # warm-up: the first call after loading is several seconds slower
    mon.reset()
    log(f"ready. Drop photos or clips into {IN}")
    while True:
        for path in sorted(IN.iterdir()):
            kind = path.suffix.lower()
            if kind not in PHOTOS | CLIPS:
                continue
            size = path.stat().st_size
            time.sleep(1.0)  # wait until the file has finished copying
            if path.stat().st_size != size:
                continue
            try:
                (do_photo if kind in PHOTOS else do_clip)(mon, path)
            except Exception as problem:  # one bad file must not stop the watcher
                log(f"ERROR | {path.name} | {problem}")
            mon.reset()  # each clip starts clean
            path.replace(DONE / path.name)
        time.sleep(1.0)


if __name__ == "__main__":
    main()
