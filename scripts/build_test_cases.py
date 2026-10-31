"""Build a folder of test cases (inputs) and run the whole system on each one (outputs), with an index page.

  python scripts/build_test_cases.py prepare "C:/Users/PRITAM/Desktop/images/test_cases"
  python scripts/build_test_cases.py run     "C:/Users/PRITAM/Desktop/images/test_cases"

prepare : picks real photos from the held-out set, cuts clips from the site videos, copies fall clips, makes darkened and silhouette variants
run     : analyses every input with the real pipeline (object check, cross-check, backlit rule) and writes annotated outputs + index.html + RESULTS.csv
Photos from the datasets keep their credits in CREDITS.md; synthetic variants are marked "synthetic" in their file names.
"""
import csv
import html
import shutil
import sys
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data" / "ppe4"
FALLS = ROOT / "data" / "falls" / "gmdcsa24" / "GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos-master"
CRANE = ROOT / "outputs" / "web_video" / "1dfb370623f4" / "clip.mp4"  # a site video with a concrete bucket on a crane, and two backlit workers
BUSY = ROOT / "outputs" / "web_video" / "56a2dc8b8901" / "clip.mp4"  # a busy site with many workers

FOLDERS = {
    "01_simple": ("Clear photos", "Large, clear workers. Each worker is judged on their own; most verdicts should be right.", None),
    "02_hard_crowded_small": ("Hard: crowded, small, distant", "Many workers or very small ones. Some will be missed or sent to review; that is the honest limit.", None),
    "03_night_low_light": ("Night and low light (synthetic)", "The clear photos darkened with brightness, gamma and noise. Accuracy drops; see the day-versus-night numbers.", None),
    "04_backlit_silhouettes": ("Backlit silhouettes", "Workers who are dark shapes against a bright background. Their gear cannot be seen, so nobody should be flagged as a violation: they should be 'needs review'.", "no_violation"),
    "05_hi_vis_and_life_jacket_lookalikes": ("Hi-vis clothing and life jackets", "Real photos of hi-vis clothing and life jackets (Wikimedia Commons, credited). Shows what the system makes of vest look-alikes; there is no single right answer, so these are for inspection.", None),
    "06_accident_fall_videos": ("Accident: a person falls", "A person falls to the ground. A WORKER DOWN alert is expected. The system cannot say why they fell.", "alert"),
    "07_collapse_unresponsive_videos": ("Collapse: down and not getting up", "A person goes down and stays down. A WORKER DOWN alert is expected. It cannot tell a heart attack from a trip or a falling object: it only says a worker is down.", "alert"),
    "08_object_not_a_worker": ("An object, not a worker", "A concrete bucket on a crane that used to be flagged as 'worker 921'. Nothing should be flagged.", "no_incident"),
    "09_live_feed_demo": ("Live feed demo", "One long video made of several of the cases above, to use as a stand-in for a live camera.", None),
    "10_busy_site_video": ("Busy site video", "A site with many workers moving about.", None),
}


# ------------------------------------------------------------------------------------------------ helpers
def labels(split: str, stem: str, w: int, h: int):
    path = DATA / "labels" / split / f"{stem}.txt"
    persons, others = [], []
    if path.exists():
        for line in path.read_text().splitlines():
            c, cx, cy, bw, bh = line.split()[:5]
            cx, cy, bw, bh = float(cx) * w, float(cy) * h, float(bw) * w, float(bh) * h
            (persons if int(c) == 0 else others).append((int(cx - bw / 2), int(cy - bh / 2), int(cx + bw / 2), int(cy + bh / 2)))
    return persons


def write_clip(frames, path: Path, fps: float, size: tuple[int, int]) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for frame in frames:
        writer.write(frame if frame.shape[1::-1] == size else cv2.resize(frame, size))
    writer.release()


def cut(video: Path, start: int, end: int, out: Path) -> None:
    cap = cv2.VideoCapture(str(video))
    fps, size = cap.get(cv2.CAP_PROP_FPS) or 25, (int(cap.get(3)), int(cap.get(4)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    frames = []
    for _ in range(end - start):
        ok, frame = cap.read()
        if not ok:
            break
        frames.append(frame)
    write_clip(frames, out, fps, size)


def silhouette(image, persons):
    """A synthetic backlit version of a photo: the workers become dark shapes and the background gets bright."""
    x = image.astype(np.float32) / 255.0
    bright = np.clip((x ** 0.7) * 1.35, 0, 1)
    mask = np.zeros(image.shape[:2], np.float32)
    for x1, y1, x2, y2 in persons:
        mask[max(0, y1):y2, max(0, x1):x2] = 1.0
    mask = cv2.GaussianBlur(mask, (0, 0), 5)[..., None]
    dark = (x ** 2.4) * 0.28
    return (np.clip(bright * (1 - mask) + dark * mask, 0, 1) * 255).astype(np.uint8)


def prepare(target: Path) -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from make_night import darken  # noqa: E402

    rng = np.random.default_rng(3)
    images = sorted((DATA / "images" / "test").glob("*"))
    simple, hard = [], []
    for path in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        h, w = img.shape[:2]
        persons = labels("test", path.stem, w, h)
        heights = [p[3] - p[1] for p in persons]
        if 1 <= len(persons) <= 3 and min(heights) >= 0.4 * h:
            simple.append((path, persons))
        elif len(persons) >= 8 or (persons and float(np.median(heights)) < 0.15 * h):
            hard.append((path, persons))
    pick = lambda items, n: [items[i] for i in np.linspace(0, len(items) - 1, n).astype(int)] if len(items) >= n else items
    simple, hard = pick(simple, 8), pick(hard, 8)

    def put(folder: str, name: str, image=None, src: Path | None = None) -> Path:
        d = target / folder / "input"
        d.mkdir(parents=True, exist_ok=True)
        out = d / name
        if src is not None:
            shutil.copy(src, out)
        else:
            cv2.imwrite(str(out), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        return out

    for i, (p, _) in enumerate(simple, 1):
        put("01_simple", f"simple_{i:02d}{p.suffix}", src=p)
    for i, (p, _) in enumerate(hard, 1):
        put("02_hard_crowded_small", f"hard_{i:02d}{p.suffix}", src=p)
    # darkened copies (synthetic) of some of the above
    for i, (p, _) in enumerate(simple[:6] + hard[:4], 1):
        put("03_night_low_light", f"night_synthetic_{i:02d}.jpg", darken(cv2.imread(str(p)), rng))
    # silhouettes: one real frame, one real clip, and some synthetic ones
    cap = cv2.VideoCapture(str(CRANE))
    cap.set(cv2.CAP_PROP_POS_FRAMES, 608)
    ok, frame = cap.read()
    if ok:
        put("04_backlit_silhouettes", "sunset_workers_real_frame.jpg", frame)
    cut(CRANE, 580, 700, target / "04_backlit_silhouettes" / "input" / "sunset_workers_real_clip.mp4") if (target / "04_backlit_silhouettes" / "input").exists() else None
    for i, (p, persons) in enumerate(simple[:3], 1):
        put("04_backlit_silhouettes", f"silhouette_synthetic_{i:02d}.jpg", silhouette(cv2.imread(str(p)), persons))
    # the crane bucket
    (target / "08_object_not_a_worker" / "input").mkdir(parents=True, exist_ok=True)
    cut(CRANE, 330, 470, target / "08_object_not_a_worker" / "input" / "concrete_bucket_on_crane.mp4")
    cap.set(cv2.CAP_PROP_POS_FRAMES, 380)
    ok, frame = cap.read()
    if ok:
        put("08_object_not_a_worker", "concrete_bucket_frame.jpg", frame)
    # fall and collapse clips (GMDCSA24: MIT licence, credited in CREDITS.md)
    # three clips from each of the four people (a low-light clip first when there is one); two people per folder
    per = {}
    for subject in range(1, 5):
        rows = list(csv.DictReader(open(FALLS / f"Subject {subject}" / "Fall.csv", encoding="utf-8")))
        clips = [(subject, r["File Name"].strip(), "night" in r.get("Time of Recording", "").lower() or "off" in r.get("Time of Recording", "").lower()) for r in rows]
        per[subject] = sorted(clips, key=lambda c: (not c[2], c[1]))[:3]
    chosen = {"06_accident_fall_videos": per[1] + per[2], "07_collapse_unresponsive_videos": per[3] + per[4]}
    for folder in chosen:
        shutil.rmtree(target / folder / "input", ignore_errors=True)
    for folder, clips in chosen.items():
        for subject, name, night in clips:
            put(folder, f"subject{subject}_{Path(name).stem}{'_lowlight' if night else ''}.mp4", src=FALLS / f"Subject {subject}" / "Fall" / name)
    # one long stand-in for a live camera: several clips one after another
    live = target / "09_live_feed_demo" / "input"
    live.mkdir(parents=True, exist_ok=True)
    parts = [BUSY, target / "08_object_not_a_worker" / "input" / "concrete_bucket_on_crane.mp4", target / "04_backlit_silhouettes" / "input" / "sunset_workers_real_clip.mp4"]
    parts += sorted((target / "06_accident_fall_videos" / "input").glob("*.mp4"))[:2]
    frames = []
    for part in parts:
        if not part.exists():
            continue
        cap = cv2.VideoCapture(str(part))
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frames.append(frame)
    write_clip(frames, live / "live_feed_demo.mp4", 24, (854, 480))
    (target / "10_busy_site_video" / "input").mkdir(parents=True, exist_ok=True)
    shutil.copy(BUSY, target / "10_busy_site_video" / "input" / "busy_site.mp4")
    (target / "CREDITS.md").write_text(
        "# Credits\n\n"
        "- Photos in 01 to 04 come from the Construction-PPE dataset (Ultralytics, AGPL-3.0) and the CHVG dataset (Ferdous and Ahsan 2022, CC BY 4.0). Files with 'synthetic' in the name were made by darkening or silhouetting those photos.\n"
        "- Photos in 05 are from Wikimedia Commons; the author and licence of each are in 05_hi_vis_and_life_jacket_lookalikes/input/CREDITS.csv.\n"
        "- Fall clips in 06 and 07 are from the GMDCSA24 dataset (MIT licence).\n"
        "- The crane and busy-site videos were supplied by the team.\n", encoding="utf-8")
    print({f: len(list((target / f / 'input').glob('*'))) for f in FOLDERS if (target / f / "input").exists()})


# ------------------------------------------------------------------------------------------------ run
def run(target: Path, only: tuple = ()) -> None:
    from ppe.annotate import crop_person, draw  # noqa: E402,F401
    from ppe.config import Config  # noqa: E402
    from ppe.crosscheck import second_opinion  # noqa: E402
    from ppe.detector import Detector  # noqa: E402
    from ppe.pipeline import analyze  # noqa: E402
    from ppe.track import process_video  # noqa: E402
    from ppe.types import NEEDS_REVIEW, VIOLATION  # noqa: E402

    weights = ROOT / "weights" / "best.pt"
    extras = ROOT / "weights" / "extras.pt"
    night = ROOT / "weights" / "best_night.pt"
    detector = Detector(str(weights), extra_weights=str(extras) if extras.exists() else None, night_weights=str(night) if night.exists() else None)
    cfg = Config()
    from ppe.fall_model import FallClassifier, PoseFallMonitor  # noqa: E402

    pose_weights, fall_spec = ROOT / "weights" / "yolo11n-pose.pt", ROOT / "weights" / "fall_model.json"
    old = list(csv.DictReader(open(target / "RESULTS.csv", encoding="utf-8"))) if (target / "RESULTS.csv").exists() and only else []
    rows = [r for r in old if not any(r["folder"].startswith(o) for o in only)]  # keep earlier results of folders that are not re-run
    for folder, (title, expectation, rule) in FOLDERS.items():
        src = target / folder / "input"
        if not src.exists() or (only and not any(folder.startswith(o) for o in only)):
            continue
        out = target / folder / "output"
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        for path in sorted(src.iterdir()):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".mp4"}:
                continue  # credits and other notes sit in the same folder
            if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
                image = cv2.imread(str(path))
                if image is None:
                    continue
                detector.reset_tracking()
                result = analyze(image, cfg, detector)
                second_opinion(image, result, detector, cfg)
                annotated = draw(image, result, prefix="Employee")
                shot = out / f"{path.stem}_result.jpg"
                cv2.imwrite(str(shot), annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
                v = [x for x in result.verdicts if x.status == VIOLATION]
                r = [x for x in result.verdicts if x.status == NEEDS_REVIEW]
                note = f"{len(result.verdicts)} workers: {len(result.verdicts) - len(v) - len(r)} OK, {len(v)} violation, {len(r)} review" + (f", {len(result.objects)} object(s)" if result.objects else "")
                if v:
                    note += " | missing: " + "; ".join(sorted({m for x in v for m in x.missing}))
                ok = (len(v) == 0) if rule in ("no_violation", "no_incident") else None
                rows.append({"folder": folder, "file": path.name, "kind": "photo", "result": note, "check": ("PASS" if ok else "FAIL") if ok is not None else "inspect", "output": shot.relative_to(target).as_posix(), "poster": shot.relative_to(target).as_posix()})
            elif path.suffix.lower() == ".mp4":
                detector.reset_tracking()
                small = replace(cfg, tile_grid=0)
                accident = rule == "alert"
                if accident:  # the question here is "is a worker down?", not "is gear worn?"
                    small = replace(small, required=("helmet",))
                learned = PoseFallMonitor(str(pose_weights), FallClassifier.load(fall_spec)) if accident and pose_weights.exists() and fall_spec.exists() else None
                video_out, evidence = out / f"{path.stem}_result.mp4", out / f"{path.stem}_evidence"
                incidents = process_video(path, small, detector, video_out, out / f"{path.stem}_incidents.csv", evidence, every_nth=2, max_frames=900, fall_pose=learned,
                                          crosscheck=lambda frame, result: second_opinion(frame, result, detector, small))
                detector.reset_tracking()
                ppe = [i for i in incidents if i["kind"] == "PPE" and not accident]
                alerts = [i for i in incidents if i["kind"] != "PPE"]
                people = len({i["worker_id"] for i in ppe})
                note = f"{len(ppe)} gear incident(s) for {people} worker(s); {len(alerts)} worker-down alert(s)"
                if alerts:
                    note += " (first at " + ", ".join(f"{a['time_s']}s" for a in alerts[:3]) + ")"
                if rule == "alert":
                    check = "PASS" if alerts else "FAIL"
                elif rule == "no_incident":
                    check = "PASS" if not incidents else "FAIL"
                elif rule == "no_violation":
                    check = "PASS" if not ppe else "FAIL"
                else:
                    check = "inspect"
                poster = None
                cap = cv2.VideoCapture(str(path))
                n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, n // 2))
                ok, frame = cap.read()
                if ok:
                    poster = out / f"{path.stem}_poster.jpg"
                    cv2.imwrite(str(poster), cv2.resize(frame, None, fx=0.6, fy=0.6))
                rows.append({"folder": folder, "file": path.name, "kind": "video", "result": note, "check": check, "output": video_out.relative_to(target).as_posix(), "poster": poster.relative_to(target).as_posix() if poster else ""})
            print(folder, path.name, "->", rows[-1]["result"], rows[-1]["check"], flush=True)  # (inside the media branches only)

    with open(target / "RESULTS.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    write_index(target, rows)


def write_index(target: Path, rows: list[dict]) -> None:
    parts = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><title>SiteGuard test cases</title><style>",
             "body{font:15px/1.5 Segoe UI,Arial,sans-serif;margin:0;background:#f5f6f8;color:#17202b}main{max-width:1150px;margin:0 auto;padding:24px}",
             "h1{margin:0 0 4px}h2{margin:28px 0 4px;border-bottom:2px solid #1d4ed8;padding-bottom:4px}.sub{color:#586374}",
             ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px;margin-top:10px}",
             ".card{background:#fff;border:1px solid #dadfe6;border-radius:8px;overflow:hidden}.card img{width:100%;height:170px;object-fit:cover;display:block;background:#0f1722}",
             ".card div{padding:8px 10px;font-size:13px}.PASS{color:#138a52;font-weight:700}.FAIL{color:#d23b3b;font-weight:700}.inspect{color:#586374;font-weight:600}",
             ".note{background:#fff7e0;border-left:4px solid #e0a000;padding:8px 12px;margin:14px 0}a{color:#1d4ed8}</style></head><body><main>",
             "<h1>SiteGuard test cases</h1><div class='sub'>Every input is in the <b>input</b> folder of its case, and what the system produced is in <b>output</b>. Open the .mp4 results in any video player.</div>",
             "<div class='note'><b>Honest reading:</b> PASS and FAIL appear only where the right answer is clear (no violation for a silhouette or an object; a worker-down alert for a fall). Everything else is for inspection. Results come from the current model; they are not a benchmark. See docs/ACCURACY_MEASURED.md for the measured numbers.</div>"]
    for folder, (title, expectation, rule) in FOLDERS.items():
        mine = [r for r in rows if r["folder"] == folder]
        if not mine:
            continue
        counts = {k: sum(1 for r in mine if r["check"] == k) for k in ("PASS", "FAIL")}
        parts.append(f"<h2>{html.escape(title)}</h2><div class='sub'>{html.escape(expectation)}"
                     + (f" &nbsp; <span class='PASS'>{counts['PASS']} pass</span> <span class='FAIL'>{counts['FAIL']} fail</span>" if rule else "") + "</div><div class='grid'>")
        for r in mine:
            parts.append(f"<div class='card'><a href='{html.escape(r['output'])}'><img src='{html.escape(r['poster'] or r['output'])}' alt=''></a>"
                         f"<div><b>{html.escape(r['file'])}</b> <span class='{r['check']}'>{r['check']}</span><br>{html.escape(r['result'])}</div></div>")
        parts.append("</div>")
    parts.append("</main></body></html>")
    (target / "index.html").write_text("".join(parts), encoding="utf-8")
    print("index written:", target / "index.html")


if __name__ == "__main__":
    mode, folder = sys.argv[1], Path(sys.argv[2])
    if mode == "run":
        run(folder, tuple(sys.argv[3:]))
    else:
        prepare(folder)
