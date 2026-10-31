"""SiteGuard: PPE compliance, penalties and escalation for construction sites. Three pages, one for each level of responsibility.

  Supervisor  - check photos, video and the live camera; record violations; approve or waive proposed penalties
  Worker      - see your own violations and penalties like a challan; acknowledge or dispute
  Authority   - the level above supervisors: escalations, supervisor oversight, analytics, rules and policy

Run:  streamlit run app.py
"""
import streamlit as st

from ppe import ui

st.set_page_config(page_title="SiteGuard | PPE Safety", page_icon=":material/shield:", layout="wide")
ui.inject_css()

navigation = st.navigation(
    [
        st.Page("views/supervisor.py", title="Supervisor", icon=":material/engineering:", default=True),
        st.Page("views/worker.py", title="Worker", icon=":material/badge:"),
        st.Page("views/authority.py", title="Authority", icon=":material/account_balance:"),
    ]
)
with st.sidebar:
    ui.brand()
navigation.run()
