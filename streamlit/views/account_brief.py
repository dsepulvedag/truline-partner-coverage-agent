"""Tier 1: strategic partner brief (internal) and partner business review (partner-shareable), side by side."""
import re
from datetime import date, timedelta

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
st.caption("The agent checks recent news (last 6 months, favoring the last 90 days) for the partner's 2 largest real-company "
           "accounts with a play this week and the 2 largest without one: expansion signals vs headwinds, and whether "
           "our play fits. Web searches use company name and domain only; no Truline data leaves Snowflake.")
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def in_window(text, cutoff):
    """Drop dated bullets ('- Feb 2026: ...') older than the cutoff month; the model sometimes ignores the window."""
    keep = []
    for line in text.splitlines():
        m = re.match(r"\s*[-*]\s*([A-Za-z]{3})[a-z]*\.?\s+(\d{4})\b", line)
        if m and m.group(1).lower() in MONTHS and (int(m.group(2)), MONTHS[m.group(1).lower()]) < (cutoff.year, cutoff.month):
            continue
        keep.append(line)
    return "\n".join(keep)


if st.button("Find why-now signals", icon=":material/travel_explore:"):
    accts = query("""
        WITH p AS (SELECT ACCOUNT_ID, LISTAGG(PLAY_TYPE || ' (expected ' || TO_VARCHAR(ROUND(VALUE_USD / 1000)) || 'K, owner '
                                       || OWNER_REP_NAME || ')', '; ') WITHIN GROUP (ORDER BY VALUE_USD DESC) AS PLAYS
                   FROM TRULINE.APP.PLAY_CANDIDATES WHERE PARTNER_ID = ? GROUP BY 1),
        a AS (SELECT a.ACCOUNT_NAME, a.DOMAIN, a.ARR_NOW, p.PLAYS, p.PLAYS IS NOT NULL AS HAS_PLAY
              FROM TRULINE.APP.ACCOUNTS a LEFT JOIN p ON p.ACCOUNT_ID = a.ACCOUNT_ID
              WHERE a.PARTNER_ID = ? AND a.IS_REAL_COMPANY AND a.STATUS = 'Active')
        SELECT * FROM a QUALIFY ROW_NUMBER() OVER (PARTITION BY HAS_PLAY ORDER BY ARR_NOW DESC) <= 2
        ORDER BY HAS_PLAY DESC, ARR_NOW DESC""", (pid, pid))
    with_play = "\n".join(f"- {r.ACCOUNT_NAME} ({r.DOMAIN}): our play this week: {r.PLAYS}"
                          for r in accts.itertuples() if r.HAS_PLAY) or "- none"
    without = "\n".join(f"- {r.ACCOUNT_NAME} ({r.DOMAIN})" for r in accts.itertuples() if not r.HAS_PLAY) or "- none"
    today = date.today()
    q = f"""Why-now check for partner {pid}. Today is {today:%B %d, %Y}.
For each account below, use WebSearch with ONLY the company name and domain (never any Truline data).
Only use developments dated ON OR AFTER {today - timedelta(days=183):%B %d, %Y} (6 months); prefer ones after
{today - timedelta(days=90):%B %d, %Y}. Discard anything older, even if it is relevant. Look for:
- Expansion signals: new investment, growth, new projects or products, new markets or regions, acquisitions, hiring.
- Headwind signals: falling revenue or profit warnings, regulatory problems, market exits, layoffs or restructuring, paused or cancelled investments.

Accounts WITH a play this week:
{with_play}

Accounts WITHOUT a play this week:
{without}

For each account write:
### <account name>
**Signal:** Expansion / Headwind / Mixed / No recent signal
- <Mon YYYY>: <finding> (<publisher>)   (1-3 bullets; every bullet MUST have a date inside the window and a source)
For accounts with a play: **Play alignment:** Aligned / Misaligned / Unclear, one sentence on why.
For accounts without a play: **Opportunity:** the play the signals suggest (expansion, renewal rescue, right-size) or none.
**Recommendation:** one sentence (e.g. push now, deprioritize, switch to proactive right-size, watch).
If nothing falls in the window write "No recent signal" and do not use older news. Never invent dates or sources."""
    with st.status("Agent researching…", expanded=False) as status:
        try:
            answer, _ = run_agent([{"role": "user", "content": [{"type": "text", "text": q}]}], status)
            status.update(label="Done", state="complete")
        except Exception as e:  # noqa: BLE001
            answer = ""
            status.update(label=f"Agent unavailable: {str(e)[:200]}", state="error")
    st.session_state[f"why_{pid}"] = in_window(answer, date.today() - timedelta(days=183))
if st.session_state.get(f"why_{pid}"):
    st.markdown(st.session_state[f"why_{pid}"].replace("$", r"\$"))
