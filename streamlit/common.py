"""Shared helpers: the caller's-rights connection, queries, formatting, identity badge."""
import json
import re

import pandas as pd
import streamlit as st

SV = "TRULINE.APP.TRULINE_COVERAGE"


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
