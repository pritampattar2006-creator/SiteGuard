"""Worker page: a worker sees their own violations and penalties, like a challan, and can respond or dispute."""
from datetime import date
from pathlib import Path

import streamlit as st

from ppe import insights, penalties, store, ui
from ppe.report import notice_pdf

if "worker_id" not in st.session_state:
    ui.hero("Worker", "Your safety record", "See what was recorded against you, the photo evidence, any penalty, and respond. Every case has a time log.",
            ["Acknowledge or dispute", "Photo evidence", "Penalties explained"])
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        with st.container(border=True):
            st.markdown("#### Sign in")
            typed = st.text_input("Employee ID", placeholder="for example E101")
            if st.button("Sign in", type="primary", width="stretch"):
                with store.connect() as conn:
                    person = store.find_worker(conn, typed)
                if person:
                    st.session_state["worker_id"] = person["employee_id"]
                    st.rerun()
                st.error("That Employee ID was not found. Ask your supervisor to add you.")
            st.caption("Demo build: your Employee ID is your login. A real deployment would add a password.")
    st.stop()

with store.connect() as conn:
    me = store.find_worker(conn, st.session_state["worker_id"])
    if me is None:
        del st.session_state["worker_id"]
        st.rerun()
    cases = store.list_violations(conn, worker_id=me["id"])
    fines = penalties.list_for_worker(conn, me["id"])
    inbox = penalties.notifications(conn, "worker", me["id"], limit=8)

issued = [p for p in fines if p["kind"] == "penalty" and p["status"] == "Issued"]
owed = sum(p["amount"] for p in issued)
score = insights.safety_score(cases)
word, colour = insights.score_label(score)
initials = "".join(part[0] for part in me["name"].split()[:2]).upper()
st.markdown(
    f'<div class="idcard"><div class="avatar">{ui.esc(initials)}</div><div class="who"><span class="muted">{ui.esc(me["level"].upper())}</span>'
    f'<h2>{ui.esc(me["name"])}</h2><div class="id">ID {ui.esc(me["employee_id"])}{" &middot; " + ui.esc(me["department"]) if me["department"] else ""}</div>'
    f'<div class="barcode"></div></div><div class="score">{ui.ring(score, "safety score", colour, 150)}'
    f'<div style="color:{colour};font-weight:700;letter-spacing:.06em;text-transform:uppercase">{word}</div></div></div>', unsafe_allow_html=True)
if st.button("Sign out"):
    del st.session_state["worker_id"]
    st.rerun()

st.write("")
ui.tiles([("Violations on record", len(cases), "all time", ui.INK, insights.daily_series(cases, 14)),
          ("Penalties issued", len(issued), "awaiting payment or dispute", ui.BAD if issued else ui.GOOD, None),
          ("Amount due", f"INR {owed:.0f}" if owed else "None", "from issued penalties", ui.BAD if owed else ui.GOOD, None),
          ("Proposed, not yet issued", sum(p["status"] == "Proposed" for p in fines), "a supervisor will decide", ui.WARN, None)])
if inbox:
    st.markdown(f'<div class="callout" style="margin-top:14px"><b>Latest:</b> {ui.esc(inbox[0]["message"])}</div>', unsafe_allow_html=True)

main, side = st.columns([2.3, 1])
with side:
    ui.section("How penalties work")
    rules = penalties.load_rules()
    st.caption(f"{rules['worker']['propose_penalty_at']} violations within {rules['window_days']} days lead to a proposed penalty. A supervisor must approve it before it is issued, "
               "and you can dispute it. Nothing is issued automatically. These are example values set by management.")
    ui.section("Activity", "your last 12 weeks")
    st.markdown(ui.calendar(insights.activity_calendar(cases)), unsafe_allow_html=True)
    tips = insights.tips_for([m.strip() for c in cases for m in c["missing"].split(",") if c["status"] != "Dismissed"])
    if tips:
        ui.section("Safety tips")
        st.markdown("".join(f'<div class="tip">{ui.esc(t)}</div>' for t in tips), unsafe_allow_html=True)

with main:
    ui.section("Penalty notices", f"{len([p for p in fines if p['kind'] == 'penalty'])} on record")
    mine = [p for p in fines if p["kind"] == "penalty"]
    if not mine:
        st.success("No penalties.")
    for p in mine:
        st.markdown(ui.penalty_ticket(p), unsafe_allow_html=True)
        if p["status"] == "Issued":
            with st.expander("Dispute this penalty"):
                reason = st.text_area("Why do you dispute it?", key=f"pd-{p['id']}")
                if st.button("Send dispute", key=f"pdb-{p['id']}"):
                    if not reason.strip():
                        st.error("Please explain why.")
                    else:
                        with store.connect() as conn:
                            penalties.decide(conn, p["id"], "Disputed", me["name"], reason)
                        st.rerun()
    ui.section("Violations", f"{len(cases)} on record")
    if not cases:
        st.success("No violations are recorded against you.")
    for r in cases:
        st.markdown(ui.ticket(r), unsafe_allow_html=True)
        x, y = st.columns(2)
        with x:
            if r["status"] == "Open":
                with st.expander("Respond"):
                    note = st.text_area("Your comment", key=f"n-{r['id']}", placeholder="Required if you dispute")
                    a, b = st.columns(2)
                    if a.button("I acknowledge", key=f"a-{r['id']}", width="stretch"):
                        with store.connect() as conn:
                            store.set_status(conn, r["id"], "Acknowledged", me["name"], note)
                        st.rerun()
                    if b.button("I dispute", key=f"d-{r['id']}", width="stretch"):
                        if not note.strip():
                            st.error("Please explain why.")
                        else:
                            with store.connect() as conn:
                                store.set_status(conn, r["id"], "Disputed", me["name"], note)
                            st.rerun()
        with y:
            with st.expander("Time log and notice"):
                with store.connect() as conn:
                    events = store.get_events(conn, r["id"])
                    pdf = notice_pdf(store.get_violation(conn, r["id"]), events)
                ui.timeline(events)
                if r["evidence_path"] and Path(r["evidence_path"]).exists():
                    st.image(r["evidence_path"], width="stretch")
                st.download_button("Download notice (PDF)", pdf, f"violation_{r['id']:05d}.pdf", "application/pdf", key=f"p-{r['id']}")
