"""Check photos and clips for phone use. One box and one short label per person, nothing else on the picture.

  python scripts/phone_check.py <folder or file> [out_folder]

Photos get <name>_phone.jpg; clips get <name>_phone.mp4 (a box is drawn only while the alert holds) and every alert is listed in phone_results.csv.
Nothing here is a violation: a person should look at what it shows.
"""
import csv
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ppe.phone import PhoneMonitor, draw_findings  # noqa: E402

PHOTOS, CLIPS = {".jpg", ".jpeg", ".png", ".bmp"}, {".mp4", ".avi", ".mov", ".mkv"}


def weights(name: str) -> str:
    return str(next(p for p in (ROOT / "weights" / name, ROOT / name) if p.exists()))


def main() -> None:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "outputs" / "phone"
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in ([src] if src.is_file() else src.iterdir()) if p.suffix.lower() in PHOTOS | CLIPS)
    mon = PhoneMonitor(weights("yolo11n-pose.pt"), weights("yolo11s.pt"), device=0)
    rows = []
    for path in files:
        if path.suffix.lower() in PHOTOS:
            image = cv2.imread(str(path))
            found = mon.look(image)
            cv2.imwrite(str(out / f"{path.stem}_phone.jpg"), draw_findings(image, found))
            rows.append([path.name, "photo", "", len(found), "; ".join(f["kind"] for f in found)])
            print(path.name, [f["kind"] for f in found])
        else:
            cap = cv2.VideoCapture(str(path))
            fps = cap.get(cv2.CAP_PROP_FPS) or 25
            size = (int(cap.get(3)), int(cap.get(4)))
            writer = cv2.VideoWriter(str(out / f"{path.stem}_phone.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
            n, step, drawn = 0, max(1, int(fps / 4)), []  # looks at about 4 frames a second; a box stays on screen while the alert holds
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                if n % step == 0:
                    for a in mon.update(n / fps, frame):
                        rows.append([path.name, "clip", a["time_s"], 1, a["kind"] + (" (review)" if a["needs_review"] else "")])
                        print(path.name, a["time_s"], a["kind"])
                    drawn = mon.active()
                writer.write(draw_findings(frame, drawn))
                n += 1
            writer.release()
    with open(out / "phone_results.csv", "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([["file", "type", "time_s", "people", "result"]] + rows)
    print("saved to", out)


if __name__ == "__main__":
    main()
