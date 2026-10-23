"""Tier 3: monthly report for a long-tail partner (no PAM). One sample on demand; the same call scales to all 200."""
import streamlit as st

from common import SV, call, cite, evidence, identity_badge, latest_doc, me, query, usd

MODEL = "claude-sonnet-4-5"

st.title("Long tail")
identity_badge()

cov = query(f"""SELECT * FROM SEMANTIC_VIEW({SV} METRICS accounts.total_arr, accounts.active_accounts
                DIMENSIONS partners.coverage_model) WHERE COVERAGE_MODEL LIKE 'Long tail%'""")
partners = query("""SELECT PARTNER_ID, PARTNER_NAME FROM TRULINE.APP.PARTNERS
                    WHERE COVERAGE_MODEL LIKE 'Long tail%' ORDER BY PARTNER_NAME""")
if partners.empty:
    st.info("No long-tail partners are visible to you.")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Long-tail partners", f"{len(partners):,}", help="Partners with no Truline PAM")
c2.metric("Their customers", f"{int(cov['ACTIVE_ACCOUNTS'].sum()):,}" if not cov.empty else "–")
c3.metric("Their ARR", usd(cov["TOTAL_ARR"].sum()) if not cov.empty else "–")
st.caption("No human covers these partners today. Each gets a monthly report written by Claude from governed data, "
           "with every number cited and internal fields withheld.")

ids = list(partners["PARTNER_ID"])
names = dict(zip(partners["PARTNER_ID"], partners["PARTNER_NAME"]))
default = ids.index("P0370") if "P0370" in ids else 0
pid = st.selectbox("Partner", ids, index=default, format_func=lambda p: f"{names[p]} ({p})",
                   disabled=me()["PERSONA"] == "Partner")

reports = st.session_state.setdefault("monthly", {})
if st.button("Generate this month's report", icon=":material/mail:", type="primary"):
    with st.status("Writing the monthly report…", expanded=True) as status:
        st.write(f"Building facts from `{SV}` (partner audience: internal fields excluded)…")
        reports[pid] = call("CALL TRULINE.APP.GENERATE_DOC('PARTNER_MONTHLY', ?, 'partner', ?)", (pid, MODEL),
                            tag="long_tail:monthly")
        status.update(label=f"Claim check {reports[pid].get('status', 'error')}", state="complete", expanded=False)

d = reports.get(pid) or latest_doc("PARTNER_MONTHLY", pid, "partner")
if d:
    if "error" in d:
        st.error(d["error"])
    else:
        st.badge(f"Claim check {d['status']} · {d['doc_id']}", color="green" if d["status"].startswith("PASS") else "red")
        st.markdown(cite(d["rendered"]))
        with st.expander("Evidence"):
            evidence(d["doc_id"])
        st.download_button("Download report (Markdown)", d["rendered"], file_name=f"{pid}_monthly_report.md",
                           icon=":material/download:")

with st.expander("How this scales to all 200 partners"):
    st.markdown("The report is one call, `GENERATE_DOC('PARTNER_MONTHLY', partner_id, 'partner', model)`. "
                "A scheduled task can run it for every long-tail partner each month; each partner user then sees "
                "only their own report (row access policy on documents and facts).")
