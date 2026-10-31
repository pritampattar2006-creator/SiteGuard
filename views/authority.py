"""Authority page: the level above supervisors. Escalations, supervisor oversight, analytics, and the rules and penalty policy."""
import json
from datetime import date, timedelta
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from ppe import insights, penalties, store, ui
from ppe.roles import load_roles

with store.connect() as conn:
    rows = store.list_violations(conn, limit=5000)
    waiting_escalations = penalties.pending(conn, "escalation")
    waiting_penalties = penalties.pending(conn, "penalty")
    inbox = penalties.notifications(conn, "authority", limit=8)
    roster = store.list_workers(conn)
    decisions = conn.execute("SELECT decided_by, status, COUNT(*) AS n FROM penalties WHERE kind = 'penalty' AND decided_by != '' GROUP BY decided_by, status").fetchall()
    issued_total = conn.execute("SELECT COALESCE(SUM(amount), 0) AS t FROM penalties WHERE kind = 'penalty' AND status IN ('Issued', 'Paid')").fetchone()["t"]
rules = penalties.load_rules()
window_start = str(date.today() - timedelta(days=rules["window_days"]))
recent = [r for r in rows if r["occurred_at"][:10] >= window_start and r["status"] != "Dismissed"]

ui.hero("Authority", "Safety oversight",
        "The level above supervisors. Review escalations, check that supervisors follow the rules themselves, and see the whole site's picture.",
        [f"{len(waiting_escalations)} escalation(s) waiting", f"{len(roster)} people on the roster", date.today().strftime("%A %d %B %Y")])
ui.tiles([("Violations, last 30 days", len(recent), "all workers", ui.BAD if recent else ui.GOOD, insights.daily_series(rows, 14)),
          ("Escalations waiting", len(waiting_escalations), "need your decision", ui.WARN if waiting_escalations else ui.GOOD, None),
          ("Penalties awaiting a supervisor", len(waiting_penalties), "proposed or disputed", ui.WARN if waiting_penalties else ui.GOOD, None),
          ("Penalties issued, total", f"INR {issued_total:.0f}", "issued and paid", ui.INK, None)])
st.write("")
esc_tab, sup_tab, analytics_tab, policy_tab = st.tabs(["Escalations", "Supervisor oversight", "Analytics", "Rules and policy"])

with esc_tab:
    left, right = st.columns([2.2, 1])
    with right:
        ui.section("Notifications")
        st.markdown(ui.feed([(n["message"], ui.pretty_time(n["at"]), ui.ORANGE) for n in inbox]) if inbox else "<span class='muted'>Nothing new.</span>", unsafe_allow_html=True)
    with left:
        ui.section("Waiting for your decision", "a person always decides; nothing formal is sent automatically")
        if not waiting_escalations:
            st.success("No escalations are waiting.")
        for p in waiting_escalations:
            st.markdown(ui.penalty_ticket(p, f"{p['level']}: {p['worker_name']} ({p['employee_id']})"), unsafe_allow_html=True)
            a, b, c = st.columns([2, 1, 1])
            note = a.text_input("Note for the record", key=f"enote-{p['id']}")
            if b.button("Uphold", key=f"up-{p['id']}", type="primary"):
                with store.connect() as conn:
                    penalties.decide(conn, p["id"], "Upheld", "Authority", note)
                st.rerun()
            if c.button("Dismiss", key=f"dis-{p['id']}"):
                with store.connect() as conn:
                    penalties.decide(conn, p["id"], "Dismissed", "Authority", note)
                st.rerun()

with sup_tab:
    ui.section("Are supervisors following the rules themselves?", "supervisors are held to the same PPE rules, with a lower escalation limit")
    sups = [w for w in roster if w["level"] == "supervisor"]
    if not sups:
        st.info("No supervisors on the roster yet. Add one with level 'supervisor' on the Supervisor page.")
    else:
        table = []
        for s in sups:
            mine = [r for r in recent if r["worker_id"] == s["id"]]
            table.append({"Supervisor": s["name"], "Employee ID": s["employee_id"], "Violations (30 days)": len(mine),
                          "Limit before escalation": rules["supervisor"]["escalate_to_authority_at"],
                          "Status": "Over the limit" if len(mine) >= rules["supervisor"]["escalate_to_authority_at"] else "Within limit"})
        st.dataframe(pd.DataFrame(table), hide_index=True, width="stretch")
    ui.section("How supervisors decide on penalties", "a supervisor who waives everything, or approves everything, is worth a conversation")
    if decisions:
        st.dataframe(pd.DataFrame([{"Supervisor": d["decided_by"], "Decision": d["status"], "Count": d["n"]} for d in decisions]), hide_index=True, width="stretch")
    else:
        st.caption("No penalty decisions yet.")

with analytics_tab:
    if not rows:
        st.info("No violations recorded yet.")
    else:
        ui.section("What the data says")
        st.markdown("".join(f'<div class="insight">{ui.esc(s)}</div>' for s in insights.sentences(rows)), unsafe_allow_html=True)
        stats = store.stats(None, rows) if False else None
        by_day = pd.Series(insights.daily_series(rows, 30), index=[str(date.today() - timedelta(days=29 - i)) for i in range(30)], name="violations")
        by_item: dict[str, int] = {}
        for r in insights.counted(rows):
            for item in (m.strip() for m in r["missing"].split(",") if m.strip()):
                by_item[item] = by_item.get(item, 0) + 1
        hourly = insights.hourly_counts(rows)
        c1, c2 = st.columns([1.6, 1])
        c1.markdown("##### Violations per day (30 days)")
        c1.altair_chart(ui.style_chart(alt.Chart(by_day.reset_index().rename(columns={"index": "day"})).mark_area(color=ui.ORANGE, opacity=.3, line={"color": ui.ORANGE, "strokeWidth": 3})
                                       .encode(x=alt.X("day:T", title=None), y=alt.Y("violations:Q", title=None, axis=alt.Axis(tickMinStep=1))).properties(height=230)), width="stretch")
        c2.markdown("##### What was missing")
        c2.altair_chart(ui.style_chart(alt.Chart(pd.DataFrame({"item": list(by_item), "n": list(by_item.values())})).mark_bar(color=ui.INK, cornerRadiusEnd=4)
                                       .encode(y=alt.Y("item:N", title=None, sort="-x"), x=alt.X("n:Q", title=None, axis=alt.Axis(tickMinStep=1))).properties(height=230)), width="stretch")
        c3, c4 = st.columns(2)
        c3.markdown("##### Time of day")
        c3.altair_chart(ui.style_chart(alt.Chart(pd.DataFrame({"hour": list(hourly), "n": list(hourly.values())})).mark_bar(color=ui.ORANGE, cornerRadiusEnd=3)
                                       .encode(x=alt.X("hour:O", title="hour"), y=alt.Y("n:Q", title=None, axis=alt.Axis(tickMinStep=1))).properties(height=230)), width="stretch")
        places = pd.Series([r["location"] or "Not set" for r in insights.counted(rows)]).value_counts().rename_axis("place").reset_index(name="n")
        c4.markdown("##### Where it happens")
        c4.altair_chart(ui.style_chart(alt.Chart(places).mark_bar(color=ui.INK, cornerRadiusEnd=4)
                                       .encode(y=alt.Y("place:N", title=None, sort="-x"), x=alt.X("n:Q", title=None, axis=alt.Axis(tickMinStep=1))).properties(height=230)), width="stretch")
        repeaters = insights.repeat_offenders(rows)
        if repeaters:
            ui.section("Repeat violators", "more than one counted violation")
            st.dataframe(pd.DataFrame([{"Person": n, "Violations": c} for n, c in repeaters]), hide_index=True, width="stretch")

with policy_tab:
    ui.section("The ten rules", "the system enforces only the ones it can check today")
    library = json.loads(Path("config/rules_library.json").read_text(encoding="utf-8-sig"))["rules"]
    st.dataframe(pd.DataFrame([{"Rule": r["name"], "Can SiteGuard check it?": "Yes" if r["detectable"] else "Not yet", "Enabled": "Yes" if r["enabled"] else "No",
                                "Severity": r["severity"], "Counts towards a penalty": "Yes" if r["counts_towards_penalty"] else "No", "Note": r["note"]} for r in library]),
                 hide_index=True, width="stretch")
    ui.section("Penalty policy", "example values: management sets the real ones in config/penalty_rules.json")
    st.markdown(f"- **{rules['worker']['propose_penalty_at']} violations** within **{rules['window_days']} days** lead to a proposed penalty of **{rules['currency']} {rules['worker']['penalty_amount']}**. "
                f"A supervisor must approve it before it is issued; the worker can dispute it.\n"
                f"- **{rules['worker']['escalate_to_authority_at']} violations** in the window also escalate the worker to you.\n"
                f"- **Supervisors** get no money penalty here; at **{rules['supervisor']['escalate_to_authority_at']} violations** in the window the case comes straight to you.\n"
                "- A dismissed violation never counts. A person always makes the final decision.")
    ui.section("Trades and what they must wear", "starter values for your safety officer to confirm")
    st.dataframe(pd.DataFrame([{"Trade": r.label, "Must wear": ", ".join(i.title() for i in r.required)} for r in load_roles().values()]), hide_index=True, width="stretch")
