"""Page 2 - Employee Portal: a worker sees the violations recorded against them and can respond."""
from datetime import datetime
from pathlib import Path

import streamlit as st

from ppe import store, ui
from ppe.report import notice_pdf

ui.hero("Employee Portal", "See what was recorded against you, the evidence, and respond. Everything has a time log.")

if "employee_id" not in st.session_state:
    _, middle, _ = st.columns([1, 1.3, 1])
    with middle:
        with st.container(border=True):
            st.markdown("#### Sign in")
            typed = st.text_input("Employee ID", placeholder="for example E101")
            if st.button("Sign in", type="primary", width="stretch"):
                with store.connect() as conn:
                    worker = store.find_worker(conn, typed)
                if worker:
                    st.session_state["employee_id"] = worker["employee_id"]
                    st.rerun()
                st.error("That Employee ID was not found. Ask your supervisor to add you to the roster.")
            st.caption("Demo build: your Employee ID is your login. A real deployment would add a password.")
    st.stop()

with store.connect() as conn:
    worker = store.find_worker(conn, st.session_state["employee_id"])
    if worker is None:
        del st.session_state["employee_id"]
        st.rerun()
    records = store.list_violations(conn, worker_id=worker["id"])

top, out = st.columns([5, 1])
top.markdown(f"### {worker['name']}  \n<span class='muted'>Employee ID {worker['employee_id']}"
             f"{' &middot; ' + worker['department'] if worker['department'] else ''}</span>"
             f"{'  ' + ui.demo_chip() if worker['is_demo'] else ''}", unsafe_allow_html=True)
if out.button("Sign out", width="stretch"):
    del st.session_state["employee_id"]
    st.rerun()

counts = {s: sum(r["status"] == s for r in records) for s in store.STATUSES}
last = max((r["occurred_at"] for r in records), default=None)
days = (datetime.now() - datetime.fromisoformat(last)).days if last else None
ui.kpi_row([
    ("Violations on record", len(records)),
    ("Waiting for your response", counts["Open"], "acknowledge or dispute", "bad" if counts["Open"] else "good"),
    ("Disputed, under review", counts["Disputed"], "", "warn" if counts["Disputed"] else ""),
    ("Days since last violation", "-" if days is None else days, "keep it going" if days is not None else "none recorded", "good"),
])
st.write("")

if not records:
    st.success("No violations are recorded against you. Thank you for working safely.")
    st.stop()

show = st.segmented_control("Show", ["All", *store.STATUSES], default="All")
visible = [r for r in records if show in (None, "All") or r["status"] == show]
if not visible:
    st.info("Nothing with that status.")

for r in visible:
    with st.container(border=True):
        img, info = st.columns([1, 2.2])
        shot = r["crop_path"] if r["crop_path"] and Path(r["crop_path"]).exists() else r["evidence_path"]
        if shot and Path(shot).exists():
            img.image(shot, width="stretch")
        with info:
            st.markdown(f"**#{r['id']:05d} &middot; {r['missing']}**  {ui.chip(r['status'])}", unsafe_allow_html=True)
            st.markdown(f"<span class='muted'>{ui.pretty_time(r['occurred_at'])} &middot; {r['location'] or 'location not set'}"
                        f" &middot; seen in the image as {r['worker_ref']}</span>", unsafe_allow_html=True)
            st.markdown(f"**What the system saw:** {r['reason'] or 'No detail recorded.'}")

            if r["status"] == "Open":
                with st.expander("Respond to this violation"):
                    note = st.text_area("Your comment", key=f"note-{r['id']}", placeholder="Required if you dispute")
                    a, b = st.columns(2)
                    if a.button("I acknowledge this", key=f"ack-{r['id']}", width="stretch"):
                        with store.connect() as conn:
                            store.set_status(conn, r["id"], "Acknowledged", worker["name"], note)
                        st.rerun()
                    if b.button("I dispute this", key=f"dis-{r['id']}", width="stretch"):
                        if not note.strip():
                            st.error("Please explain why you are disputing it.")
                        else:
                            with store.connect() as conn:
                                store.set_status(conn, r["id"], "Disputed", worker["name"], note)
                            st.rerun()

            with st.expander("Time log and full photo"):
                with store.connect() as conn:
                    events = store.get_events(conn, r["id"])
                ui.timeline(events)
                if r["evidence_path"] and Path(r["evidence_path"]).exists():
                    st.image(r["evidence_path"], caption="Full evidence photo", width="stretch")
            with store.connect() as conn:
                pdf = notice_pdf(store.get_violation(conn, r["id"]), store.get_events(conn, r["id"]))
            st.download_button("Download notice (PDF)", pdf, f"violation_{r['id']:05d}.pdf", "application/pdf", key=f"pdf-{r['id']}")
