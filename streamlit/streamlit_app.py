"""Truline partner coverage workbench (Streamlit in Snowflake, container runtime).

Every query runs on a restricted caller's-rights connection: the viewer's own Snowflake user and default role,
so row access and masking policies decide what each persona sees. Pages are chosen by persona.
"""
import streamlit as st

st.set_page_config(page_title="Truline coverage", page_icon=":material/hub:", layout="wide")

# Must be created at the top level of the script (the caller token is only valid at session start).
if "conn" not in st.session_state:
    st.session_state["conn"] = st.connection("snowflake-callers-rights")

from common import me  # noqa: E402

persona = me()["PERSONA"]

weekly = st.Page("views/weekly_plan.py", title="Weekly plan", icon=":material/checklist:")
brief = st.Page("views/account_brief.py", title="Account brief", icon=":material/description:")
long_tail = st.Page("views/long_tail.py", title="Long tail", icon=":material/stacks:")
agent = st.Page("views/agent.py", title="Ask the agent", icon=":material/smart_toy:")
audit = st.Page("views/audit.py", title="Audit and policies", icon=":material/verified_user:")

coverage = {"Shared PAM": [weekly], "Dedicated PAM": [brief], "Partner": [long_tail],
            "Coverage ops": [weekly, brief, long_tail], "Admin": [weekly, brief, long_tail]}.get(persona, [])
nav = st.navigation({"Your coverage": coverage + [agent], "Trust": [audit]} if coverage else {"Trust": [audit]})
st.sidebar.caption("Truline partner coverage agent")
nav.run()
