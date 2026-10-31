"""Page 3 - Violation Register: the admin panel, like an e-challan register, with analytics and PDF reports."""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from ppe import store, ui
from ppe.report import notice_pdf, summary_pdf

ui.hero("Violation Register", "Every recorded violation with its evidence, status and time log. Filter, resolve and export reports.")

with store.connect() as conn:
    roster = store.list_workers(conn)
worker_options = {"All workers": None} | {f"{w['name']} ({w['employee_id']})": w["id"] for w in roster}

# ---- filters -----------------------------------------------------------------------------------
f1, f2, f3, f4, f5 = st.columns([1.5, 1, 1.3, 1, 1.3])
period = f1.date_input("Period", (date.today() - timedelta(days=30), date.today()))
status = f2.selectbox("Status", ["All", *store.STATUSES])
worker_pick = f3.selectbox("Worker", list(worker_options))
item = f4.selectbox("Violation", ["All", "NO HELMET", "NO VEST"])
search = f5.text_input("Search", placeholder="name, ID, place, photo")
since, until = (period if isinstance(period, tuple) and len(period) == 2 else (None, None))

with store.connect() as conn:
    rows = store.list_violations(
        conn, worker_id=worker_options[worker_pick], status=None if status == "All" else status,
        missing=None if item == "All" else item, since=str(since) if since else None,
        until=str(until) if until else None, text=search or None,
    )
    stats = store.stats(conn, rows)

ui.kpi_row([
    ("Violations", stats["total"]),
    ("Open", stats["by_status"]["Open"], "not yet answered", "bad" if stats["by_status"]["Open"] else ""),
    ("Disputed", stats["by_status"]["Disputed"], "needs your decision", "warn" if stats["by_status"]["Disputed"] else ""),
    ("Resolved", stats["by_status"]["Resolved"], "", "good"),
    ("Workers involved", len(stats["by_worker"])),
])
st.write("")
register_tab, analytics_tab, workers_tab, reports_tab = st.tabs(["Register", "Analytics", "Workers", "Reports"])

# ---- register ----------------------------------------------------------------------------------
with register_tab:
    if not rows:
        st.info("No violations match these filters. Record some on the Supervisor Console, or load demo data in the Workers tab.")
    else:
        table = pd.DataFrame([{
            "ID": f"{r['id']:05d}", "When": ui.pretty_time(r["occurred_at"]), "Worker": r["worker_name"] or f"Unassigned ({r['worker_ref']})",
            "Violation": r["missing"], "Location": r["location"], "Source": r["source"], "Status": r["status"],
        } for r in rows])
        picked = st.dataframe(table, hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row", key="register_table")
        selected = picked.selection.rows
        if not selected:
            st.caption("Click a row to open the case.")
        else:
            record = rows[selected[0]]
            with store.connect() as conn:
                events = store.get_events(conn, record["id"])
            st.markdown(f"### Case #{record['id']:05d}  {ui.chip(record['status'])}"
                        f"{'  ' + ui.demo_chip() if record['is_demo'] else ''}", unsafe_allow_html=True)
            left, right = st.columns([3, 2])
            with left:
                if record["evidence_path"] and Path(record["evidence_path"]).exists():
                    st.image(record["evidence_path"], caption="Evidence photo", width="stretch")
                if record["crop_path"] and Path(record["crop_path"]).exists():
                    st.image(record["crop_path"], caption="Worker close-up", width=260)
            with right:
                st.markdown(f"**Worker:** {record['worker_name'] or 'Not assigned'}"
                            f"{' (' + record['employee_id'] + ')' if record['employee_id'] else ''}  \n"
                            f"**Violation:** {record['missing']}  \n**When:** {ui.pretty_time(record['occurred_at'])}  \n"
                            f"**Location:** {record['location'] or '-'}  \n**Seen in image as:** {record['worker_ref']}  \n"
                            f"**Source:** {record['source_name'] or record['source']}"
                            + (f" at {record['video_time_s']:.1f} s" if record["video_time_s"] is not None else "") + "  \n"
                            f"**Why flagged:** {record['reason'] or '-'}")
                st.markdown("##### Time log")
                ui.timeline(events)

            st.markdown("##### Actions")
            a1, a2, a3 = st.columns([1.2, 1.6, 1])
            new_status = a1.selectbox("Change status to", store.STATUSES, index=store.STATUSES.index(record["status"]), key="new_status")
            note = a2.text_input("Note for the time log", key="status_note")
            if a3.button("Update status", type="primary", width="stretch"):
                with store.connect() as conn:
                    store.set_status(conn, record["id"], new_status, "Supervisor", note)
                st.rerun()
            b1, b2 = st.columns([2, 1])
            assign_to = b1.selectbox("Assign to worker", list(worker_options), key="assign_to")
            if b2.button("Assign", width="stretch", disabled=assign_to == "All workers"):
                with store.connect() as conn:
                    store.assign_worker(conn, record["id"], worker_options[assign_to], "Supervisor")
                st.rerun()
            with store.connect() as conn:
                pdf = notice_pdf(store.get_violation(conn, record["id"]), store.get_events(conn, record["id"]))
            st.download_button("Download this case as a PDF notice", pdf, f"violation_{record['id']:05d}.pdf", "application/pdf")

# ---- analytics ---------------------------------------------------------------------------------
with analytics_tab:
    if not rows:
        st.info("Nothing to chart for these filters.")
    else:
        c1, c2 = st.columns(2)
        c1.markdown("##### Violations per day")
        c1.bar_chart(pd.Series(stats["by_day"], name="violations"))
        c2.markdown("##### By missing item")
        c2.bar_chart(pd.Series(stats["by_item"], name="violations"))
        c3, c4 = st.columns(2)
        c3.markdown("##### By worker")
        c3.bar_chart(pd.Series(stats["by_worker"], name="violations"), horizontal=True)
        c4.markdown("##### By status")
        c4.bar_chart(pd.Series(stats["by_status"], name="violations"))

# ---- workers -----------------------------------------------------------------------------------
with workers_tab:
    st.markdown("##### Roster")
    st.caption("The AI numbers the people in a photo (\"Worker 3\") but does not recognise faces. A supervisor attaches the real name from this roster.")
    if roster:
        st.dataframe(pd.DataFrame([{"Employee ID": w["employee_id"], "Name": w["name"], "Department": w["department"],
                                    "Demo": "yes" if w["is_demo"] else ""} for w in roster]), hide_index=True, width="stretch")
    else:
        st.info("No workers yet. Add one below, or load demo data.")
    with st.form("add_worker", clear_on_submit=True):
        a, b, c = st.columns(3)
        emp_id, name, dept = a.text_input("Employee ID"), b.text_input("Name"), c.text_input("Department")
        if st.form_submit_button("Add worker"):
            try:
                with store.connect() as conn:
                    store.add_worker(conn, emp_id, name, dept)
                st.rerun()
            except ValueError as problem:
                st.error(str(problem))

    st.markdown("##### Demo data")
    st.caption("For presentations: creates four demo workers (DEMO01-DEMO04) and records the real violations the model finds in "
               "`eval/test_images`, assigned to them. Everything is marked DEMO DATA.")
    if st.button("Load demo data"):
        from ppe.demo import seed_demo

        with st.spinner("Analysing the sample photos..."):
            with store.connect() as conn:
                count = seed_demo(conn, ui.load_detector(ui.find_weights()))
        st.success(f"Recorded {count} demo violation(s). Sign in as DEMO01 on the Employee Portal to see a worker's view.")

# ---- reports -----------------------------------------------------------------------------------
with reports_tab:
    st.markdown("##### PDF summary report")
    st.caption("Uses the filters above. Contains headline counts and a time log with each worker's name, the violation and the evidence image.")
    label = f"{since} to {until}" if since and until else "All dates"
    if rows:
        st.download_button("Download summary report (PDF)", summary_pdf(rows, stats, "PPE Violation Summary", label),
                           f"ppe_violation_summary_{date.today()}.pdf", "application/pdf", type="primary")
        export = pd.DataFrame([{
            "id": r["id"], "occurred_at": r["occurred_at"], "worker": r["worker_name"] or "", "employee_id": r["employee_id"] or "",
            "seen_as": r["worker_ref"], "violation": r["missing"], "location": r["location"], "status": r["status"],
            "reason": r["reason"], "source": r["source_name"] or r["source"],
        } for r in rows])
        st.download_button("Download data (CSV)", export.to_csv(index=False).encode("utf-8"), f"ppe_violations_{date.today()}.csv", "text/csv")
        st.dataframe(export.head(8), hide_index=True, width="stretch")
    else:
        st.info("No violations match these filters, so there is nothing to report yet.")
