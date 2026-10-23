"""Shared helpers: the caller's-rights connection, queries, formatting, identity badge."""
import json
import re

import pandas as pd
import requests
import streamlit as st

SV = "TRULINE.APP.TRULINE_COVERAGE"
AGENT = "TRULINE/schemas/APP/agents/TRULINE_COVERAGE_AGENT"


def conn():
    """Caller's-rights connection created at the top of streamlit_app.py (viewer's identity, policies apply)."""
    return st.session_state["conn"]


def run(sql, params=None, tag=None):
    cur = conn().cursor()
    if tag:
        cur.execute(f"ALTER SESSION SET QUERY_TAG = 'truline:{tag}'")
    cur.execute(sql, params)
    return cur.fetch_pandas_all() if cur.description else None


@st.cache_data(ttl=600, scope="session", show_spinner=False)
def query(sql, params=None):
    return run(sql, params)


def call(proc_sql, params=None, tag=None):
    df = run(proc_sql, params, tag)
    val = df.iloc[0, 0]
    return json.loads(val) if isinstance(val, str) else val


def usd(v):
    if v is None or pd.isna(v):
        return "–"
    a = abs(v)
    return f"${v/1e9:.2f}B" if a >= 1e9 else f"${v/1e6:.1f}M" if a >= 1e6 else f"${v/1e3:.0f}K" if a >= 1e3 else f"${v:,.0f}"


def pct(v):
    return "–" if v is None or pd.isna(v) else f"{v*100:.1f}%"


def me():
    if "me" not in st.session_state:
        st.session_state["me"] = query("SELECT * FROM TRULINE.APP.MY_SCOPE").iloc[0].to_dict()
    return st.session_state["me"]


def identity_badge():
    m = me()
    persona = m["PERSONA"] or "No coverage assigned"
    st.badge(f"{m['USER_NAME']} · {persona} · {m['PARTNERS_VISIBLE']} of {m['PARTNERS_TOTAL']} partners visible by policy"
             f" · data as of {pd.to_datetime(m['DATA_AS_OF']):%b %Y}", icon=":material/lock:", color="green")


def cite(text):
    """Turn '$5.1M [F3]' citations into inline badges ($ escaped so Markdown doesn't read it as LaTeX)."""
    return re.sub(r"\[(F\d+)\]", r":blue-badge[\1]", text.replace("$", r"\$"))


def evidence(doc_id):
    facts = query("""SELECT FACT_ID, LABEL, DISPLAY, METRIC, SOURCE_OBJECT, QUERY_ID FROM TRULINE.APP.DOC_FACTS
                     WHERE DOC_ID = ? ORDER BY TO_NUMBER(SUBSTR(FACT_ID, 2))""", (doc_id,))
    st.dataframe(facts, hide_index=True, use_container_width=True,
                 column_config={"FACT_ID": "Fact", "LABEL": "Meaning", "DISPLAY": "Value",
                                "METRIC": "Governed metric (semantic view)", "SOURCE_OBJECT": "Source", "QUERY_ID": "Query ID"})


def run_agent(messages, status):
    """Call the Cortex Agent REST API as the viewer (caller's-rights session token); returns (text, tables)."""
    raw = conn()._instance
    r = requests.post(f"https://{raw.host}/api/v2/databases/{AGENT}:run",
                      json={"messages": messages}, stream=True, timeout=300,
                      headers={"Authorization": f'Snowflake Token="{raw.rest.token}"',
                               "Accept": "text/event-stream", "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    r.encoding = "utf-8"
    event, text, tables = None, [], []
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        if line.startswith("event:"):
            event = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        try:
            data = json.loads(line[5:].strip() or "{}")
        except json.JSONDecodeError:  # e.g. a bare "[DONE]" marker
            continue
        if not isinstance(data, dict):
            continue
        if event == "response.text.delta":
            text.append(data.get("text", ""))
        elif event == "response.status" and data.get("message"):
            status.write(data["message"])
        elif event == "response.tool_use":
            status.write(f"Tool: `{data.get('name') or data.get('type')}`")
        elif event == "response.table":
            rs = data.get("result_set", {})
            cols = [c["name"] for c in rs.get("resultSetMetaData", {}).get("rowType", [])]
            if cols:
                tables.append({"columns": cols, "rows": rs.get("data", [])})
        elif event == "error":
            raise RuntimeError(data.get("message", str(data)))
    return "".join(text).strip(), tables


def latest_doc(doc_type, subject_id, audience, statuses=("PASS", "PASS_WITH_WARNINGS")):
    """Most recent saved document of this kind for the viewer (RAP_OWN_ROWS), shaped like GENERATE_DOC's result."""
    marks = ", ".join("?" * len(statuses))
    df = run(f"""SELECT DOC_ID, CHECK_STATUS, RENDERED, CREATED_AT FROM TRULINE.APP.DOCUMENTS
                 WHERE DOC_TYPE = ? AND SUBJECT_ID = ? AND AUDIENCE = ? AND CHECK_STATUS IN ({marks}) AND RENDERED IS NOT NULL
                 ORDER BY CREATED_AT DESC LIMIT 1""", (doc_type, subject_id, audience, *statuses))
    if df is None or df.empty:
        return None
    r = df.iloc[0]
    facts = run("""SELECT FACT_ID, LABEL, INTERNAL_ONLY FROM TRULINE.APP.DOC_FACTS WHERE DOC_ID = ?""", (r["DOC_ID"],))
    return {"doc_id": r["DOC_ID"], "status": r["CHECK_STATUS"], "rendered": r["RENDERED"], "saved_at": r["CREATED_AT"],
            "facts": [{"id": f.FACT_ID, "label": f.LABEL, "internal_only": bool(f.INTERNAL_ONLY)} for f in facts.itertuples()]}
