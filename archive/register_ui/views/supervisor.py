"""Page 1 - Supervisor Console: check photos and video, then record violations against named workers."""
import shutil
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
import streamlit as st

from ppe import insights, store, ui
from ppe.annotate import draw
from ppe.config import Config
from ppe.evidence import EVIDENCE_DIR
from ppe.pipeline import analyze
from ppe.service import record_video_incident, record_violations, violation_rows
from ppe.summary import summarize, to_csv_bytes, to_json_bytes, workers_table
from ppe.track import process_video
from ppe.types import ITEM_NAMES

SAMPLES = Path("eval/test_images")

# ---- sidebar: detection settings ---------------------------------------------------------------
with st.sidebar:
    st.markdown("##### Detection settings")
    weights = st.text_input("Model weights", ui.find_weights())
    extras = ui.find_extra_weights()
    person_conf = st.slider("Person confidence", 0.05, 0.9, Config.person_conf, 0.05)
    helmet_conf = st.slider("Helmet confidence", 0.05, 0.9, Config.helmet_conf, 0.05)
    vest_conf = st.slider("Vest confidence", 0.05, 0.9, Config.vest_conf, 0.05)
    enhance = st.selectbox("Low-light enhancement", ["auto", "on", "off"])
    tiles = st.checkbox("Look for small / background workers (slower)", value=True,
                        help="Also checks four zoomed-in pieces of the photo. Finds more far-away workers, with a few extra false boxes.")
    if extras:
        goggles_conf = st.slider("Goggles confidence", 0.05, 0.9, Config.goggles_conf, 0.05)
        gloves_conf = st.slider("Gloves confidence", 0.05, 0.9, Config.gloves_conf, 0.05)
        boots_conf = st.slider("Boots confidence", 0.05, 0.9, Config.boots_conf, 0.05)
    else:
        goggles_conf, gloves_conf, boots_conf = Config.goggles_conf, Config.gloves_conf, Config.boots_conf

if not Path(weights).exists():
    ui.hero("Supervisor console", "Model not found", f"No model at {weights}. Train one with scripts/train.py or fix the path in the sidebar.")
    st.stop()
detector = ui.load_detector(weights, extras)
available = detector.available_items

with store.connect() as conn:
    roster = store.list_workers(conn)
    all_rows = store.list_violations(conn, limit=2000)
    week = store.check_totals(conn, since=str(date.today() - timedelta(days=6)))
    recent = all_rows[:6]
options = {"Unassigned": None} | {f"{w['name']} ({w['employee_id']})": w["id"] for w in roster}

# ---- rule set ----------------------------------------------------------------------------------
PRESETS = {
    "Construction  (helmet, vest)": ("helmet", "vest"),
    "Full kit  (all five)": tuple(available),
    "Eyes and hands  (goggles, gloves)": ("goggles", "gloves"),
    "Custom": None,
}
PRESETS = {name: items for name, items in PRESETS.items() if items is None or set(items) <= set(available)}

ui.hero("Supervisor console", "Site control",
        "Check photos and video for protective equipment, then record each violation against a named worker.",
        [f"Checks: {', '.join(ITEM_NAMES[i] for i in available)}", f"{len(roster)} workers on roster", date.today().strftime("%A %d %B %Y")])

today_count = sum(r["occurred_at"][:10] == str(date.today()) and r["status"] != "Dismissed" for r in all_rows)
open_cases = sum(r["status"] in ("Open", "Disputed") for r in all_rows)
ui.tiles([
    ("Violations today", today_count, "recorded in the register", ui.BAD if today_count else ui.GOOD, insights.daily_series(all_rows)),
    ("Open cases", open_cases, "waiting for an answer", ui.WARN if open_cases else ui.GOOD, None),
    ("Compliance, last 7 days", "-" if week["rate"] is None else f"{week['rate']}%",
     f"{week['workers']} workers checked" if week["workers"] else "no checks logged yet", ui.GOOD, None),
    ("Workers on roster", len(roster), "named workers", ui.INK, None),
])

left, right = st.columns([2.1, 1])
with left:
    ui.section("Rule set", "what every worker must wear")
    choice = st.segmented_control("Rule set", list(PRESETS), default=list(PRESETS)[0], label_visibility="collapsed")
    chosen = PRESETS.get(choice or list(PRESETS)[0])
    if chosen is None:
        chosen = tuple(st.multiselect("Required equipment", available, default=["helmet", "vest"], format_func=ITEM_NAMES.get))
    if not extras:
        st.caption("Gloves, boots and goggles need the second model (`weights/extras.pt`); only helmet and vest are available right now.")
    ui.section("Where and when")
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 1])
    location = c1.text_input("Location / camera", "Main site")
    recorded_by = c2.text_input("Recorded by", "Supervisor")
    day = c3.date_input("Date captured", datetime.now().date())
    clock = c4.time_input("Time captured", datetime.now().time().replace(second=0, microsecond=0))
    captured_at = datetime.combine(day, clock)
with right:
    ui.section("Recent activity")
    if recent:
        st.markdown(ui.feed([(f"#{r['id']:05d} {r['missing']}", f"{r['worker_name'] or r['worker_ref']} - {ui.pretty_time(r['occurred_at'])}",
                              ui.STATUS_COLOUR[r["status"]]) for r in recent]), unsafe_allow_html=True)
    else:
        st.caption("Nothing recorded yet. Check a photo and save a violation to start the register.")

if not chosen:
    st.warning("Pick at least one item to check.")
    st.stop()

cfg = replace(Config(), required=tuple(chosen), person_conf=person_conf, helmet_conf=helmet_conf, vest_conf=vest_conf,
              goggles_conf=goggles_conf, gloves_conf=gloves_conf, boots_conf=boots_conf, tile_grid=2 if tiles else 0)
settings_key = f"{weights}|{extras}|{chosen}|{person_conf}|{helmet_conf}|{vest_conf}|{goggles_conf}|{gloves_conf}|{boots_conf}|{enhance}|{tiles}"

with st.expander("Worker not in the list? Add them"):
    a, b, c, d = st.columns([1, 1.4, 1, 0.8])
    new_id, new_name, new_dept = a.text_input("Employee ID"), b.text_input("Name"), c.text_input("Department")
    if d.button("Add worker", width="stretch"):
        try:
            with store.connect() as conn:
                store.add_worker(conn, new_id, new_name, new_dept)
            st.rerun()
        except ValueError as problem:
            st.error(str(problem))

st.session_state.setdefault("checks", {})
st.session_state.setdefault("saved", {})
st.session_state.setdefault("logged", set())


class SampleFile:
    """A photo from eval/test_images, used like an uploaded file."""

    def __init__(self, path: Path):
        self.name, self._bytes = path.name, path.read_bytes()
        self.size = len(self._bytes)

    def getvalue(self) -> bytes:
        return self._bytes


photo_tab, sample_tab, video_tab = st.tabs(["Photo check", "Try a sample", "Video check"])
with sample_tab:
    samples = sorted(p.name for p in SAMPLES.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")) if SAMPLES.exists() else []
    if samples:
        pick = st.selectbox("Sample photo", samples)
        st.caption("Real site photos supplied by the team. Useful for a quick demo without uploading anything.")
        sample = SampleFile(SAMPLES / pick) if st.toggle("Check this sample", value=False) else None
    else:
        sample = None
        st.info("No sample photos found in eval/test_images.")

with photo_tab:
    uploaded = st.file_uploader("Upload worker photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    files = list(uploaded or []) + ([sample] if sample else [])
    if not files:
        st.info("Upload one or more photos, or switch on a sample in the next tab. Each worker gets a verdict, and confirmed violations can be saved to the register.")

    for file in files:
        key = f"{file.name}-{file.size}-{settings_key}"
        if key not in st.session_state["checks"]:
            image = cv2.imdecode(np.frombuffer(file.getvalue(), np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                st.error(f"{file.name}: this file could not be read as an image.")
                continue
            result = analyze(image, cfg, detector, enhance)
            st.session_state["checks"][key] = (image, draw(image, result), result)
        image, annotated, result = st.session_state["checks"][key]
        summary = summarize(result)
        if key not in st.session_state["logged"]:  # remember the check so a compliance rate can be worked out
            with store.connect() as conn:
                store.log_check(conn, source_name=file.name, location=location, workers=summary["total_workers"], compliant=summary["compliant"],
                                violations=summary["violations"], needs_review=summary["needs_review"], at=captured_at.isoformat(timespec="seconds"))
            st.session_state["logged"].add(key)

        ui.section(file.name, f"{summary['total_workers']} workers found" + (" - low-light enhancement applied" if result.enhanced else ""))
        left, right = st.columns([3, 2])
        left.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), width="stretch")
        with right:
            a, b = st.columns(2)
            a.markdown(ui.tile("Compliant", summary["compliant"], "", ui.GOOD), unsafe_allow_html=True)
            b.markdown(ui.tile("Violations", summary["violations"], "", ui.BAD if summary["violations"] else ui.GOOD), unsafe_allow_html=True)
            st.write("")
            if result.verdicts:
                st.markdown("".join(ui.worker_card(v) for v in result.verdicts), unsafe_allow_html=True)
            else:
                st.info("No workers detected in this photo.")
        if result.verdicts:
            with st.expander("Table view and downloads"):
                st.dataframe(workers_table(result).drop(columns="Reason"), hide_index=True, width="stretch")
                d1, d2 = st.columns(2)
                d1.download_button("Table (CSV)", to_csv_bytes(result), f"{Path(file.name).stem}_workers.csv", "text/csv", key=f"csv-{key}")
                d2.download_button("Summary (JSON)", to_json_bytes(result), f"{Path(file.name).stem}_summary.json", "application/json", key=f"json-{key}")

        rows = violation_rows(result)
        if summary["needs_review"]:
            st.caption(f"{summary['needs_review']} worker(s) need a manual look and are not recorded automatically.")
        if not rows:
            st.success("No confirmed violations in this photo.")
            continue

        ui.section("Record violations", "tick the ones to save, and name the worker")
        if key in st.session_state["saved"]:
            ids = ", ".join(f"#{i:05d}" for i in st.session_state["saved"][key])
            st.success(f"Saved to the register as {ids}. Find them on the Violation Register page.")
            continue
        picks = {}
        for verdict, _ in rows:
            ca, cb = st.columns([2, 2])
            keep = ca.checkbox(f"Worker {verdict.worker_id}: {', '.join(verdict.missing)}", value=True, key=f"keep-{key}-{verdict.worker_id}")
            who = cb.selectbox("Assign to", list(options), key=f"who-{key}-{verdict.worker_id}", label_visibility="collapsed")
            if keep:
                picks[verdict.worker_id] = options[who]
        if st.button(f"Save {len(picks)} violation(s) to the register", type="primary", disabled=not picks, key=f"save-{key}"):
            with store.connect() as conn:
                st.session_state["saved"][key] = record_violations(
                    conn, image_bgr=image, annotated_bgr=annotated, result=result, picks=picks, source="photo",
                    source_name=file.name, occurred_at=captured_at, location=location, recorded_by=recorded_by,
                )
            st.rerun()

with video_tab:
    st.caption("Each worker is followed through the clip. A violation is confirmed only if it lasts several frames, so one-frame flicker is ignored.")
    clip = st.file_uploader("Upload a short clip (10-30 seconds works best)", type=["mp4", "avi", "mov"])
    v1, v2 = st.columns(2)
    every_nth = v1.slider("Analyse every Nth frame (higher = faster)", 1, 6, 2)
    max_frames = v2.slider("Maximum frames to read", 100, 1200, 600, 100)

    if clip and st.button("Analyse video", type="primary"):
        run_dir = Path("outputs/video_runs") / Path(clip.name).stem
        run_dir.mkdir(parents=True, exist_ok=True)
        source = run_dir / clip.name
        source.write_bytes(clip.getvalue())
        with st.spinner("Analysing frames..."):
            incidents = process_video(source, replace(cfg, tile_grid=0), detector, run_dir / "annotated.mp4",
                                      run_dir / "incidents.csv", run_dir / "evidence", every_nth=every_nth, max_frames=max_frames)
        st.session_state["video"] = {"name": clip.name, "run_dir": str(run_dir), "incidents": incidents, "saved": False}

    video = st.session_state.get("video")
    if video:
        incidents, run_dir = video["incidents"], Path(video["run_dir"])
        st.success(f"{video['name']}: {len(incidents)} confirmed violation(s).")
        picks = {}
        for i, incident in enumerate(incidents):
            ca, cb, cc = st.columns([1, 2, 2])
            ca.image(str(run_dir / "evidence" / incident["evidence"]), width="stretch")
            cb.markdown(f"**Worker {incident['worker_id']}: NO {incident['missing_item'].upper()}**  \nat {incident['time_s']} s into the clip")
            keep = cc.checkbox("Record", value=True, key=f"vkeep-{i}")
            who = cc.selectbox("Assign to", list(options), key=f"vwho-{i}", label_visibility="collapsed")
            if keep:
                picks[i] = options[who]
        if incidents and not video["saved"]:
            if st.button(f"Save {len(picks)} violation(s) to the register", type="primary", disabled=not picks):
                EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
                with store.connect() as conn:
                    for i, worker_id in picks.items():
                        evidence = EVIDENCE_DIR / f"{Path(video['name']).stem}_{incidents[i]['evidence']}"
                        shutil.copy(run_dir / "evidence" / incidents[i]["evidence"], evidence)
                        record_video_incident(conn, incident=incidents[i], evidence_file=str(evidence), worker_id=worker_id,
                                              source_name=video["name"], started_at=captured_at, location=location, recorded_by=recorded_by)
                video["saved"] = True
                st.rerun()
        elif video["saved"]:
            st.success("Saved to the register.")
        if (run_dir / "annotated.mp4").exists():
            st.download_button("Download annotated video (MP4)", (run_dir / "annotated.mp4").read_bytes(), "annotated.mp4", "video/mp4")
