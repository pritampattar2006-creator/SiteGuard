"""Supervisor page: check photos, video and a live camera; record violations; review and approve penalties."""
import time
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import streamlit as st

from ppe import penalties, store, ui
from ppe.annotate import draw
from ppe.config import Config
from ppe.incident import FallMonitor
from ppe.pipeline import analyze
from ppe.report import summary_pdf
from ppe.roles import load_roles, usable_items
from ppe.service import record_video_incident, record_violations, violation_rows
from ppe.summary import summarize, to_csv_bytes, to_json_bytes, workers_table
from ppe.track import PersistenceFilter, TrackingView, process_video
from ppe.types import ITEM_NAMES

WEIGHT_CANDIDATES = ["weights/best.pt", "weights/best_v3.pt", "weights/best_v2.pt"]
EXTRAS = "weights/extras.pt"
VIDEO_RUNS = Path("outputs/video_runs")
MODES = {"Fast": "One model, one pass.", "Balanced": "Recommended: plus zoomed tiles for small workers.",
         "Ensemble (experimental)": "Two models. Steadier vests, but can accept a cap as a helmet."}

try:
    ROLES = load_roles()
    RULES = penalties.load_rules()
except (ValueError, KeyError) as problem:
    st.error(f"A config file has a problem: {problem}")
    st.stop()

# ---- sidebar -----------------------------------------------------------------------------------
with st.sidebar:
    st.markdown("##### Detection settings")
    weights = st.text_input("Model weights", next((p for p in WEIGHT_CANDIDATES if Path(p).exists()), WEIGHT_CANDIDATES[0]))
    if not Path(weights).exists():
        ui.hero("Supervisor", "Model not found", f"No model at {weights}.")
        st.stop()
    has_extras = Path(EXTRAS).exists()
    modes = [m for m in MODES if not m.startswith("Ensemble") or has_extras]
    mode = st.radio("Accuracy mode (photos)", modes, index=modes.index("Balanced"))
    st.caption(MODES[mode])
    detector = ui.load_detector(weights, EXTRAS if has_extras else None, mode.startswith("Ensemble"))
    role_keys = [*ROLES, "custom"]
    role_key = st.selectbox("Trade / task", role_keys, format_func=lambda k: "Custom (choose items)" if k == "custom" else ROLES[k].label)
    if role_key == "custom":
        required = tuple(st.multiselect("Required equipment", detector.available_items, default=["helmet", "vest"], format_func=ITEM_NAMES.get))
    else:
        required, missing_models = usable_items(ROLES[role_key], detector.available_items)
        st.caption("Must wear: " + ", ".join(ITEM_NAMES[i] for i in ROLES[role_key].required))
        spec = ROLES[role_key]
        if missing_models:
            st.warning("Needs the second model to check: " + ", ".join(ITEM_NAMES[i] for i in missing_models))
    person_conf = st.slider("Person confidence", 0.05, 0.9, Config.person_conf, 0.05)
    helmet_conf = st.slider("Helmet confidence", 0.05, 0.9, Config.helmet_conf, 0.05)
    vest_conf = st.slider("Vest confidence", 0.05, 0.9, Config.vest_conf, 0.05)
    enhance = st.selectbox("Low-light enhancement", ["auto", "on", "off"])
    show_objects = st.checkbox("Also show helmets and vests nobody is wearing", value=False)
    st.markdown("##### Where and who")
    location = st.text_input("Location / camera", "Main site")
    recorded_by = st.text_input("Recorded by", "Supervisor")

if not required:
    st.warning("Nothing to check for this trade with the loaded models. Pick another trade.")
    st.stop()

cfg = replace(Config(), required=tuple(required), person_conf=person_conf, helmet_conf=helmet_conf, vest_conf=vest_conf,
              tile_grid=0 if mode == "Fast" else 2)

with store.connect() as conn:
    roster = store.list_workers(conn)
    new_alerts = penalties.notifications(conn, "supervisor", limit=5)
    waiting = penalties.pending(conn, "penalty")
who_options = {"Unassigned": None} | {f"{w['name']} ({w['employee_id']})": w["id"] for w in roster}


def settle(conn, worker_ids) -> list[int]:
    """After violations are saved against named workers, apply the penalty policy. Returns what was created."""
    made = []
    for wid in {w for w in worker_ids if w is not None}:
        made += penalties.check_worker(conn, wid, RULES)
    return made


ui.hero("Supervisor", "Site control", f"Check photos, video and the live camera. Record violations against named workers and decide on penalties. Trade: "
        f"{ROLES[role_key].label if role_key != 'custom' else 'custom'}.",
        [f"Checking: {', '.join(ITEM_NAMES[i] for i in required)}", f"{len(waiting)} penalties awaiting your decision", date.today().strftime("%A %d %B %Y")])
check_tab, video_tab, review_tab, live_tab = st.tabs(["Check photos", "Check video", "Review and penalties", "Live camera"])


def down_alert(text: str) -> None:
    st.markdown(f'<div style="background:#fbeaf6;border:2px solid #aa2896;border-left:10px solid #aa2896;border-radius:10px;padding:12px 16px;margin:8px 0">'
                f'<b style="color:#7a1a6a">CHECK NOW</b><br>{ui.esc(text)}</div>', unsafe_allow_html=True)


# ---- photos ------------------------------------------------------------------------------------
with check_tab:
    files = st.file_uploader("Upload worker photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    if not files:
        st.info("Upload photos. Each worker is judged against what their trade must wear.")
    when = datetime.combine(date.today(), datetime.now().time().replace(second=0, microsecond=0))
    for file in files or []:
        image = cv2.imdecode(np.frombuffer(file.read(), np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            st.error(f"{file.name}: could not be read as an image.")
            continue
        result = analyze(image, cfg, detector, enhance)
        summary = summarize(result)
        annotated = draw(image, result, show_unassigned=show_objects)
        ui.section(file.name, f"{summary['total_workers']} workers")
        if summary["possible_down"]:
            down_alert(f"{summary['possible_down']} person(s) lie flat on the ground. A photo cannot say why: please check on them now.")
        left, right = st.columns([3, 2])
        left.image(cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB), width="stretch")
        with right:
            a, b = st.columns(2)
            a.markdown(ui.tile("Compliant", summary["compliant"], "", ui.GOOD), unsafe_allow_html=True)
            b.markdown(ui.tile("Violations", summary["violations"], "", ui.BAD if summary["violations"] else ui.GOOD), unsafe_allow_html=True)
            st.write("")
            st.markdown("".join(ui.worker_card(v) for v in result.verdicts) or "No workers detected.", unsafe_allow_html=True)
        rows = violation_rows(result)
        if rows:
            with st.expander(f"Record {len(rows)} violation(s) against named workers"):
                picks = {}
                for verdict, _ in rows:
                    x, y = st.columns(2)
                    keep = x.checkbox(f"Worker {verdict.worker_id}: {', '.join(verdict.missing)}", value=True, key=f"keep-{file.name}-{verdict.worker_id}")
                    who = y.selectbox("Assign to", list(who_options), key=f"who-{file.name}-{verdict.worker_id}", label_visibility="collapsed")
                    if keep:
                        picks[verdict.worker_id] = who_options[who]
                if st.button(f"Save {len(picks)} to the register", disabled=not picks, key=f"save-{file.name}", type="primary"):
                    with store.connect() as conn:
                        ids = record_violations(conn, image_bgr=image, annotated_bgr=annotated, result=result, picks=picks, source="photo",
                                                source_name=file.name, occurred_at=when, location=location, recorded_by=recorded_by)
                        made = settle(conn, picks.values())
                    st.success("Saved as " + ", ".join(f"#{i:05d}" for i in ids) + (f". {len(made)} penalty or escalation proposed: see Review and penalties." if made else "."))
        d1, d2, d3 = st.columns(3)
        stem = Path(file.name).stem
        d1.download_button("Annotated image", cv2.imencode(".png", annotated)[1].tobytes(), f"{stem}_annotated.png", "image/png", key=f"png-{file.name}")
        d2.download_button("Table (CSV)", to_csv_bytes(result), f"{stem}_workers.csv", "text/csv", key=f"csv-{file.name}")
        d3.download_button("Summary (JSON)", to_json_bytes(result), f"{stem}_summary.json", "application/json", key=f"json-{file.name}")

# ---- video -------------------------------------------------------------------------------------
with video_tab:
    st.write("Each worker is followed through the clip. A missing item is confirmed only when it lasts several frames. A person who falls and stays down raises an alert.")
    clip = st.file_uploader("Upload a short clip", type=["mp4", "avi", "mov", "mkv"])
    c1, c2 = st.columns(2)
    every_nth = c1.slider("Analyse every Nth frame", 1, 6, 2)
    max_frames = c2.slider("Maximum frames to read", 100, 1800, 600, 100)
    can_learn = Path("weights/fall_model.json").exists() and Path("weights/yolo11n-pose.pt").exists()
    use_learned = st.checkbox("Also use the learned fall detector (experimental)", value=False, disabled=not can_learn,
                              help="Trained on 160 acted indoor falls. Measured per clip: it caught about 53% of falls (24% in low light) and gave a false alarm on 7% of normal clips "
                                   "(sitting or lying down on purpose). Slower. An alert means someone should check, not that a fall is certain.")
    if clip is not None and st.button("Analyse video", type="primary"):
        from ppe.fall_model import FallClassifier, PoseFallMonitor

        learned = PoseFallMonitor("weights/yolo11n-pose.pt", FallClassifier.load("weights/fall_model.json")) if use_learned and can_learn else None
        run_dir = VIDEO_RUNS / Path(clip.name).stem
        run_dir.mkdir(parents=True, exist_ok=True)
        source = run_dir / clip.name
        source.write_bytes(clip.getvalue())
        bar = st.progress(0.0, text="Analysing frames...")
        try:
            incidents = process_video(source, replace(cfg, tile_grid=0), detector, run_dir / "annotated.mp4", run_dir / "incidents.csv", run_dir / "evidence",
                                      every_nth=every_nth, max_frames=max_frames, progress=lambda d, t: bar.progress(min(d / t, 1.0), text=f"Frame {d} of {t}"),
                                      fall_pose=learned)
            st.session_state["video_result"] = {"name": clip.name, "dir": str(run_dir), "incidents": incidents, "saved": False}
        except ValueError as problem:
            st.error(str(problem))
        finally:
            bar.empty()
    res = st.session_state.get("video_result")
    if res and (clip is None or res["name"] == clip.name):
        run_dir, incidents = Path(res["dir"]), res["incidents"]
        alerts = [i for i in incidents if i.get("kind") in ("FALL", "DOWN", "FALL_MODEL")]
        ppe_inc = [i for i in incidents if i.get("kind", "PPE") == "PPE"]
        m1, m2 = st.columns(2)
        m1.metric("Worker down alerts", len(alerts))
        m2.metric("Confirmed PPE violations", len(ppe_inc))
        for a in alerts:
            down_alert(f"Worker {a['worker_id']} at {a['time_s']} s: {a.get('detail', '')}")
            st.image(str(run_dir / "evidence" / a["evidence"]), width=420)
        if ppe_inc:
            cols = st.columns(3)
            for i, inc in enumerate(ppe_inc):
                cols[i % 3].image(str(run_dir / "evidence" / inc["evidence"]), width="stretch", caption=f"Worker {inc['worker_id']}: no {inc['missing_item']} at {inc['time_s']} s")
            if not res["saved"] and st.button("Save these to the register (unassigned)", key="save-video"):
                with store.connect() as conn:
                    for inc in ppe_inc:
                        record_video_incident(conn, incident=inc, evidence_file=str(run_dir / "evidence" / inc["evidence"]), worker_id=None,
                                              source_name=res["name"], started_at=datetime.now(), location=location, recorded_by=recorded_by)
                res["saved"] = True
        vf = run_dir / "annotated.mp4"
        if vf.exists():
            st.video(vf.read_bytes())
            st.download_button("Annotated video", vf.read_bytes(), "annotated.mp4", "video/mp4", key="dl-video")

# ---- review and penalties ----------------------------------------------------------------------
with review_tab:
    left, right = st.columns([2.2, 1])
    with right:
        ui.section("Notifications")
        if new_alerts:
            st.markdown(ui.feed([(n["message"], ui.pretty_time(n["at"]), ui.ORANGE) for n in new_alerts]), unsafe_allow_html=True)
        else:
            st.caption("Nothing new.")
    with left:
        ui.section("Penalties waiting for your decision", "nothing is issued until you approve it")
        if not waiting:
            st.success("No penalties are waiting.")
        for p in waiting:
            st.markdown(ui.penalty_ticket(p, f"{p['worker_name']} ({p['employee_id']})"), unsafe_allow_html=True)
            a, b, c = st.columns([2, 1, 1])
            note = a.text_input("Note", key=f"pnote-{p['id']}", placeholder="Why approve or waive?")
            if b.button("Approve and issue", key=f"app-{p['id']}", type="primary"):
                with store.connect() as conn:
                    penalties.decide(conn, p["id"], "Issued", recorded_by, note)
                st.rerun()
            if c.button("Waive", key=f"wav-{p['id']}"):
                with store.connect() as conn:
                    penalties.decide(conn, p["id"], "Waived", recorded_by, note)
                st.rerun()
    with st.expander("Demo data for presentations"):
        st.caption("Creates made-up demo people (DEMO01 to DEMO04, a supervisor and a safety officer), records the real violations the model finds in `eval/test_images`, "
                   "and applies the real penalty policy, so every page has something to show. Everything is marked as demo data.")
        if st.button("Load demo data"):
            from ppe.demo import seed_demo

            with st.spinner("Analysing the sample photos..."):
                with store.connect() as conn:
                    count = seed_demo(conn, detector)
            st.success(f"Recorded {count} demo violation(s). Sign in as DEMO01 on the Worker page; the Authority page shows the escalation about the demo supervisor.")
            st.rerun()
    ui.section("Workers", "names are attached by a supervisor; the system never recognises faces")
    if roster:
        st.dataframe(pd.DataFrame([{"Employee ID": w["employee_id"], "Name": w["name"], "Level": w["level"], "Department": w["department"]} for w in roster]),
                     hide_index=True, width="stretch")
    with st.form("add_worker", clear_on_submit=True):
        a, b, c, d = st.columns(4)
        emp_id, name, dept, level = a.text_input("Employee ID"), b.text_input("Name"), c.text_input("Department"), d.selectbox("Level", store.LEVELS)
        if st.form_submit_button("Add person"):
            try:
                with store.connect() as conn:
                    store.add_worker(conn, emp_id, name, dept, level=level)
                st.rerun()
            except ValueError as problem:
                st.error(str(problem))
    with store.connect() as conn:
        recent = store.list_violations(conn, limit=200)
        stats = store.stats(conn, recent)
    ui.section("Recent cases", f"{len(recent)} shown")
    if recent:
        st.dataframe(pd.DataFrame([{"Case": f"{r['id']:05d}", "When": ui.pretty_time(r["occurred_at"]), "Worker": r["worker_name"] or f"Unassigned ({r['worker_ref']})",
                                    "Violation": r["missing"], "Location": r["location"], "Status": r["status"]} for r in recent]), hide_index=True, width="stretch")
        st.download_button("Summary report (PDF)", summary_pdf(recent, stats, "PPE Violation Summary", "Recent cases"), f"ppe_summary_{date.today()}.pdf", "application/pdf")

# ---- live camera (last, because its loop holds the page while it runs) -------------------------
with live_tab:
    st.write("Watches a camera connected to this computer. Each worker is tracked; a missing item is confirmed only when it lasts several frames, "
             "and a person who falls and stays down raises an alert. Switch it off to stop.")
    c1, c2, c3 = st.columns(3)
    camera = c1.number_input("Camera number", 0, 9, 0)
    skip = c2.slider("Analyse every Nth frame", 1, 8, 3)
    limit_s = c3.slider("Stop after (seconds)", 10, 900, 120, 10)
    run = st.toggle("Start live camera")
    frame_box, event_box = st.empty(), st.empty()
    if run:
        cap = cv2.VideoCapture(int(camera), cv2.CAP_DSHOW)
        if not cap.isOpened():
            st.error("Could not open that camera. Check it is connected, not used by another app, and the camera number is right.")
        else:
            live_cfg = replace(cfg, tile_grid=0)
            persistence, monitor, view = PersistenceFilter(cfg.persist_window, cfg.persist_min), FallMonitor(cfg), TrackingView(detector)
            started, n, events = time.time(), 0, []
            try:
                while time.time() - started < limit_s:
                    ok, frame = cap.read()
                    if not ok:
                        st.warning("The camera stopped sending frames.")
                        break
                    n += 1
                    if n % skip:
                        continue
                    result = analyze(frame, live_cfg, view)
                    now_s = time.time() - started
                    for v in result.verdicts:
                        for item in cfg.required:
                            if persistence.update(v.worker_id, item, v.states.get(item, "NOT_REQUIRED")):
                                events.append({"Time (s)": round(now_s), "Worker": v.worker_id, "Event": f"NO {item.upper()}"})
                    for alert in monitor.update(now_s, result.people):
                        events.append({"Time (s)": round(now_s), "Worker": alert["worker_id"], "Event": f"WORKER DOWN ({alert['kind']})"})
                    frame_box.image(cv2.cvtColor(draw(frame, result, show_unassigned=False), cv2.COLOR_BGR2RGB), width="stretch")
                    if events:
                        event_box.dataframe(pd.DataFrame(events), hide_index=True, width="stretch")
            finally:
                cap.release()
            st.info("Live camera stopped. Confirmed events are listed above; record serious ones from a saved photo or clip.")
