"""Ask the Truline Coverage Agent (Cortex Agent, Claude orchestration) as yourself.

The request uses the viewer's caller's-rights session token, so the agent's tools run as the viewer and
row access / masking policies apply to every answer.
"""
import streamlit as st

from common import identity_badge, run_agent

SAMPLES = ["Which of my partners need me this week, and why?",
           "What are the top 5 plays by expected ARR and who owns them?",
           "Why now for Fidelity Investments? Check the news, then our plays.",
           "Write a partner-shareable business review for P0096."]

st.title("Ask the agent")
identity_badge()
st.caption("Truline Coverage Agent: Claude orchestrates governed metrics (semantic view), web search "
           "(company name and domain only), cited documents, approvals and the audit log. It answers as you.")


if "agent_chat" not in st.session_state:
    st.session_state["agent_chat"] = []
chat = st.session_state["agent_chat"]

for m in chat:
    with st.chat_message(m["role"]):
        st.markdown(m["text"].replace("$", r"\$"))
        for t in m.get("tables", []):
            st.dataframe([dict(zip(t["columns"], row)) for row in t["rows"]], use_container_width=True)

pick = st.pills("Try", SAMPLES, selection_mode="single", label_visibility="collapsed") if not chat else None
prompt = st.chat_input("Ask about your partners, plays, accounts or documents") or pick
if prompt:
    chat.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    messages = [{"role": m["role"], "content": [{"type": "text", "text": m["text"]}]} for m in chat]
    with st.chat_message("assistant"):
        with st.status("Agent working…", expanded=False) as status:
            try:
                answer, tables = run_agent(messages, status)
                status.update(label="Done", state="complete")
            except Exception as e:  # noqa: BLE001 - show any API failure to the user
                answer, tables = "", []
                status.update(label="The agent API is not reachable from this app", state="error")
                st.info("Use the same agent in **Snowflake Intelligence** (AI & ML → Snowflake Intelligence → "
                        "Truline Coverage Agent). Details: " + str(e)[:300])
        if answer:
            st.markdown(answer.replace("$", r"\$"))
            for t in tables:
                st.dataframe([dict(zip(t["columns"], row)) for row in t["rows"]], use_container_width=True)
            chat.append({"role": "assistant", "text": answer, "tables": tables})
        else:
            chat.pop()
