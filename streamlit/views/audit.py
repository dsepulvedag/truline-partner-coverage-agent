"""Trust: audit trail, claim checks, active policies, and the "catch a made-up number" demo."""
import streamlit as st

from common import call, cite, identity_badge, me, query

st.title("Audit and policies")
identity_badge()

m = me()
st.caption(f"Signed in as **{m['USER_NAME']}** with role **{m['ROLE_NAME']}**. Rows below are filtered by row access "
           "policies on your Snowflake user, not by this app.")

st.subheader("Catch a made-up number")
docs = query("""SELECT DOC_ID, DOC_TYPE, SUBJECT_ID, AUDIENCE, CREATED_AT, DRAFT FROM TRULINE.APP.DOCUMENTS
                WHERE CHECK_STATUS IN ('PASS', 'PASS_WITH_WARNINGS') AND DRAFT IS NOT NULL
                QUALIFY ROW_NUMBER() OVER (PARTITION BY DOC_ID ORDER BY CREATED_AT DESC) = 1
                ORDER BY CREATED_AT DESC LIMIT 10""")
if docs.empty:
    st.caption("Generate a document first (Weekly plan → Run this week's plan).")
else:
    pick = st.selectbox("Document", docs["DOC_ID"],
                        format_func=lambda d: "{0} · {1} {2} ({3})".format(d, *docs.set_index("DOC_ID").loc[d, ["DOC_TYPE", "SUBJECT_ID", "AUDIENCE"]]))
    fake = st.text_input("Sentence to slip into the draft", "Renewals will grow to $4.7M next quarter, a 12% lift.")
    if st.button("Inject and re-check", icon=":material/bug_report:"):
        draft = docs.set_index("DOC_ID").loc[pick, "DRAFT"] + "\n\n" + fake
        res = call("CALL TRULINE.APP.CHECK_CLAIMS(?, ?)", (pick, draft), tag="audit:claim_check_demo")
        if res["status"] == "PASS":
            st.success("Claim check passed.")
        else:
            st.error(f"Blocked: {len(res['violations'])} number(s) are not backed by a cited fact. Logged as CLAIM_CHECK_FAIL.",
                     icon=":material/block:")
            st.dataframe(res["violations"], use_container_width=True)
        query.clear()

st.subheader("Recent actions")
log = query("""SELECT EVENT_TS, USER_NAME, ROLE_NAME, ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS
               FROM TRULINE.APP.AUDIT_LOG ORDER BY EVENT_TS DESC LIMIT 100""")
st.dataframe(log, hide_index=True, use_container_width=True)

st.subheader("Documents and claim checks")
d = query("""SELECT CREATED_AT, DOC_ID, DOC_TYPE, SUBJECT_ID, AUDIENCE, CHECK_STATUS, CREATED_BY, RENDERED
             FROM TRULINE.APP.DOCUMENTS WHERE CHECK_STATUS <> 'FACTS_READY' ORDER BY CREATED_AT DESC LIMIT 25""")
st.dataframe(d.drop(columns=["RENDERED"]), hide_index=True, use_container_width=True)
if not d.empty:
    with st.expander("Latest rendered document"):
        st.markdown(cite(d.iloc[0]["RENDERED"] or ""))

st.subheader("Policies in force")
st.markdown("""
- **`RAP_PARTNER_SCOPE`** (row access) on accounts, partners, reps, credits, plays: a row is visible only if its partner is in your coverage (`CORE.USER_SCOPE`, keyed on `CURRENT_USER()`).
- **`RAP_OWN_ROWS`** on audit log, facts and documents: your own rows; coverage ops sees all.
- **`MP_INTERNAL_NUMBER` / `MP_INTERNAL_TEXT`** (masking): churn probability, risk drivers and escalation reasons are hidden from partner users.
- **Claim checker** (`CHECK_CLAIMS`): any number in a generated document that is not a cited fact is rejected and logged.
- **Caller's rights**: this app queries as you (restricted caller's rights), so all of the above applies to what you see here.
""")
