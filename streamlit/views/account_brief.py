"""Tier 1: strategic partner brief (internal) and partner business review (partner-shareable), side by side."""
import re

import streamlit as st

from common import SV, call, cite, evidence, identity_badge, pct, query, run_agent, usd

MODEL = "claude-sonnet-4-5"

st.title("Account brief")
identity_badge()

partners = query("""SELECT PARTNER_ID, PARTNER_NAME, PAM_NAME FROM TRULINE.APP.PARTNERS
                    WHERE COVERAGE_MODEL = 'Dedicated PAM' ORDER BY CURRENT_MANAGED_ARR DESC""")
if partners.empty:
    st.info("No dedicated-PAM partners are visible to you.")
    st.stop()
labels = {r.PARTNER_ID: f"{r.PARTNER_NAME} ({r.PARTNER_ID}) · PAM {r.PAM_NAME}" for r in partners.itertuples()}
pid = st.selectbox("Partner", list(labels), format_func=labels.get)
assert re.fullmatch(r"P\d+", pid)

k = query(f"""SELECT * FROM SEMANTIC_VIEW({SV}
              METRICS accounts.total_arr, accounts.active_accounts, accounts.nrr, accounts.at_risk_arr, plays.play_value
              WHERE partners.partner_id = '{pid}')""").iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Partner ARR", usd(k["TOTAL_ARR"]), help="accounts.total_arr")
c2.metric("NRR (12 mo)", pct(k["NRR"]), help="accounts.nrr")
c3.metric("At-risk ARR", usd(k["AT_RISK_ARR"]), help="accounts.at_risk_arr")
c4.metric("Plays this week", usd(k["PLAY_VALUE"]), help="plays.play_value (expected ARR impact)")

docs = st.session_state.setdefault("briefs", {})
if st.button("Generate brief and partner review", icon=":material/description:", type="primary"):
    with st.status("Writing both versions…", expanded=True) as status:
        for audience, label in (("internal", "internal strategic brief"), ("partner", "partner-shareable review")):
            st.write(f"Building facts from `{SV}` and drafting the {label} with Claude…")
            d = call("CALL TRULINE.APP.GENERATE_DOC('PARTNER', ?, ?, ?)", (pid, audience, MODEL), tag=f"brief:{audience}")
            docs[(pid, audience)] = d
            st.write(f"{label.capitalize()}: claim check **{d.get('status', d.get('error'))}**.")
        status.update(label="Both versions ready", state="complete", expanded=False)

internal, partner = docs.get((pid, "internal")), docs.get((pid, "partner"))
if internal or partner:
    left, right = st.columns(2, gap="large")
    for col, d, title in ((left, internal, "Internal strategic brief"), (right, partner, "Partner-shareable review")):
        with col:
            st.subheader(title)
            if not d or "error" in d:
                st.error((d or {}).get("error", "Not generated"))
                continue
            st.badge(f"Claim check {d['status']} · {d['doc_id']}", color="green" if d["status"].startswith("PASS") else "red")
            st.markdown(cite(d["rendered"]))
            with st.expander("Evidence"):
                evidence(d["doc_id"])
    if internal and "facts" in internal:
        names = [f["label"] for f in internal["facts"] if f.get("internal_only")]
        st.caption("Withheld from the partner version by policy (internal-only facts): "
                   + (", ".join(names) if names else "none"))
    if partner and "rendered" in partner:
        st.download_button("Download partner version (Markdown)", partner["rendered"], file_name=f"{pid}_business_review.md",
                           icon=":material/download:")

st.divider()
st.subheader("Why now")
st.caption("The agent searches the web for the partner's largest real-company accounts using company name and domain only; "
           "no Truline metrics leave Snowflake.")
if st.button("Find why-now signals", icon=":material/travel_explore:"):
    top = query("""SELECT ACCOUNT_NAME, DOMAIN FROM TRULINE.APP.ACCOUNTS
                   WHERE PARTNER_ID = ? AND IS_REAL_COMPANY AND STATUS = 'Active' ORDER BY ARR_NOW DESC LIMIT 3""", (pid,))
    names = ", ".join(f"{r.ACCOUNT_NAME} ({r.DOMAIN})" for r in top.itertuples())
    q = (f"For partner {pid}, give a short 'why now' for each of these real customer accounts: {names}. "
         "Use web search with the company name and domain only. Then name the matching plays (play type, value, owner rep).")
    with st.status("Agent researching…", expanded=False) as status:
        try:
            answer, _ = run_agent([{"role": "user", "content": [{"type": "text", "text": q}]}], status)
            status.update(label="Done", state="complete")
        except Exception as e:  # noqa: BLE001
            answer = ""
            status.update(label=f"Agent unavailable: {str(e)[:200]}", state="error")
    st.session_state[f"why_{pid}"] = answer
if st.session_state.get(f"why_{pid}"):
    st.markdown(st.session_state[f"why_{pid}"].replace("$", r"\$"))
