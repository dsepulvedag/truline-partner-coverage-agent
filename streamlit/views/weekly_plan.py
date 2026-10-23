"""Tier 2: weekly delegation plan for a shared PAM (~20 partners)."""
import json
import re

import pandas as pd
import streamlit as st

from common import SV, call, cite, evidence, identity_badge, me, pct, query, usd

MODEL = "claude-sonnet-4-5"

head, badge = st.columns([3, 2], vertical_alignment="center")
head.title("Weekly delegation plan")
with badge:
    identity_badge()

m = me()
if m["PERSONA"] == "Shared PAM":
    pam_id = m["PAM_ID"]
else:
    pams = query("""SELECT PAM_ID, ANY_VALUE(PAM_NAME) AS PAM_NAME, COUNT(*) AS PARTNERS FROM TRULINE.APP.PARTNERS
                    WHERE COVERAGE_MODEL = 'Shared PAM' GROUP BY 1 ORDER BY 2""")
    if pams.empty:
        st.info("No shared-PAM partners are visible to you.")
        st.stop()
    labels = {r.PAM_ID: f"{r.PAM_NAME} ({r.PARTNERS} partners)" for r in pams.itertuples()}
    ids = list(labels)
    pam_id = st.selectbox("Plan for PAM", ids, index=ids.index("TP054") if "TP054" in ids else 0, format_func=labels.get)

assert re.fullmatch(r"TP\d+", pam_id)
kpi = query(f"""SELECT * FROM SEMANTIC_VIEW({SV}
                METRICS accounts.total_arr, accounts.at_risk_arr, accounts.nrr, plays.play_count, plays.play_value
                WHERE partners.pam_id = '{pam_id}')""").iloc[0]
plays = query("SELECT * FROM TRULINE.APP.PLAY_CANDIDATES WHERE PAM_ID = ? ORDER BY PAM_RANK", (pam_id,))
done = set(query("""SELECT CANDIDATE_ID FROM TRULINE.APP.PLAYS WHERE WEEK_OF = DATE_TRUNC('week', CURRENT_DATE())""")["CANDIDATE_ID"])

c1, c2, c3, c4 = st.columns(4)
c1.metric("Portfolio ARR", usd(kpi["TOTAL_ARR"]), help="accounts.total_arr (semantic view)")
c2.metric("At-risk ARR", usd(kpi["AT_RISK_ARR"]), help="accounts.at_risk_arr: At Risk + Critical accounts")
c3.metric("Plays proposed", f"{int(kpi['PLAY_COUNT'] or 0):,}", help="Plays at or above the weekly value floor")
c4.metric("Expected ARR impact", usd(kpi["PLAY_VALUE"]), help="plays.play_value: probability/win-rate weighted")

# ---- the agent run: each step is a real query or call, shown as it happens
plan_key = f"plan_doc_{pam_id}"
if st.button("Run this week's plan", icon=":material/play_arrow:", type="primary"):
    with st.status("Building the weekly plan…", expanded=True) as status:
        st.write(f"Read governed metrics from `{SV}`: {usd(kpi['TOTAL_ARR'])} ARR, NRR {pct(kpi['NRR'])}.")
        st.write(f"Scored {len(plays):,} play candidates (dynamic table `PLAY_CANDIDATES`, rules in `PLAY_PARAMS`).")
        st.write(f"Ranked by expected ARR impact; top play {usd(plays['VALUE_USD'].max())}.")
        reps = plays.groupby("OWNER_REP_NAME").size()
        st.write(f"Assigned owner reps: {reps.size} reps, {int((reps > 5).sum())} over the weekly cap of 5.")
        esc = plays[plays["ROUTED_TO"] != "Rep"]
        st.write(f"Escalated {len(esc)} plays to you; {plays.loc[plays['PARTNER_NEEDS_INTERVENTION'], 'PARTNER_ID'].nunique()} partner(s) need intervention.")
        st.write(f"Claude drafts the plan summary (`AI_COMPLETE`, {MODEL}) and the claim checker verifies every number…")
        doc = call("CALL TRULINE.APP.GENERATE_DOC('PAM_PORTFOLIO', ?, 'internal', ?)", (pam_id, MODEL), tag="weekly_plan:generate")
        st.session_state[plan_key] = doc
        if "error" in doc:
            status.update(label=doc["error"], state="error")
        else:
            cited = len(set(re.findall(r"\[(F\d+)\]", doc["rendered"])))
            st.write(f"Claim check: **{doc['status']}** ({cited} facts cited, attempt {doc['attempts']}).")
            status.update(label=f"Plan ready · claim check {doc['status']}", state="complete", expanded=False)

doc = st.session_state.get(plan_key)
if doc and "error" not in doc:
    with st.expander(f"Plan summary · claim check {doc['status']} · {doc['doc_id']}", expanded=True):
        st.markdown(cite(doc["rendered"]))
        if doc.get("misused"):
            st.warning("Label check notes: " + "; ".join(x.get("why", "") for x in doc["misused"]))
        st.caption("Evidence: every number above is a fact with a governed metric and the query that produced it.")
        evidence(doc["doc_id"])

st.divider()
left, right = st.columns([3, 2], gap="large")

with left:
    view = st.segmented_control("Show", ["Needs your approval", "Delegated to reps", "All"], default="Needs your approval")
    families = st.pills("Play family", ["Rescue", "Credits", "Expansion"], selection_mode="multi",
                        default=["Rescue", "Credits", "Expansion"])
    shown = plays[plays["PLAY_FAMILY"].isin(families or [])]
    if view == "Needs your approval":
        shown = shown[shown["ROUTED_TO"] != "Rep"]
    elif view == "Delegated to reps":
        shown = shown[shown["ROUTED_TO"] == "Rep"]
    limit = st.select_slider("Cards", [10, 20, 50, 100], value=10)
    rep_plays = plays[(plays["ROUTED_TO"] == "Rep") & ~plays["CANDIDATE_ID"].isin(done)]
    picks = {}
    with st.form("approve_form", border=False):
        for r in shown.head(limit).itertuples():
            with st.container(border=True):
                t, v = st.columns([4, 1])
                real = " :material/public:" if r.IS_REAL_COMPANY else ""
                t.markdown(f"**#{r.PAM_RANK} · {r.PLAY_TYPE}** — {r.ACCOUNT_NAME}{real}")
                v.markdown(f"**{usd(r.VALUE_USD)}**")
                st.caption(f"{r.PARTNER_NAME} · owner {r.OWNER_REP_NAME} ({r.OWNER_REP_TITLE}) · "
                           f"renews in {int(r.MONTHS_TO_RENEWAL)} mo · {r.SEGMENT}")
                if r.PLAY_FAMILY == "Rescue":
                    why = f"health change {r.HEALTH_SCORE_CHANGE_3M:+.0f} in 3 mo, seat use {pct(r.SEAT_UTILIZATION)}"
                elif r.PLAY_FAMILY == "Credits":
                    why = f"burn pace {r.BURN_PACE:.2f}x in contract month {r.CONTRACT_MONTH:.0f}"
                elif r.PLAY_TYPE == "Seat expansion":
                    why = f"seat use {pct(r.SEAT_UTILIZATION)}"
                else:
                    why = f"most peers own {r.PRODUCT_NAME}"
                st.markdown(f"{r.TRIGGER_METRICS}: {why} · value = {r.VALUE_BASIS.lower()}")
                a, b = st.columns([1.4, 3], vertical_alignment="center")
                if r.CANDIDATE_ID in done:
                    a.badge("Approved", icon=":material/check:", color="green")
                else:
                    picks[r.CANDIDATE_ID] = a.checkbox("Approve", key=f"ok_{r.CANDIDATE_ID}")
                if r.ESCALATION_REASON:
                    b.badge(f"Escalated to {r.ROUTED_TO.lower()}: {r.ESCALATION_REASON.lower()}", color="orange")
        if len(shown) > limit:
            st.caption(f"{len(shown) - limit} more plays in this view.")
        approve = st.form_submit_button("Approve ticked plays", type="primary", icon=":material/done_all:")
    delegate = st.button(f"Delegate all {len(rep_plays)} rep plays", disabled=rep_plays.empty, icon=":material/forward:")
    selected = [c for c, ok in picks.items() if ok]
    if approve and not selected:
        st.warning("Tick at least one play to approve.")
    ids = selected if approve else list(rep_plays["CANDIDATE_ID"]) if delegate else []
    if ids:
        res = call("CALL TRULINE.APP.APPROVE_PLAYS(PARSE_JSON(?)::ARRAY, ?)", (json.dumps(ids), "weekly plan"),
                   tag="weekly_plan:approve")
        st.toast(f"{res['created']} plays written to PLAYS and AUDIT_LOG"
                 + (f" · {res['not_created']} skipped ({res['reason_if_not_created']})" if res["not_created"] else ""),
                 icon=":material/task_alt:")
        query.clear()
        st.rerun()

with right:
    st.subheader("Rep load this week")
    load = (plays.groupby(["OWNER_REP_NAME", "PARTNER_NAME"])
            .agg(PLAYS=("CANDIDATE_ID", "size"), VALUE=("VALUE_USD", "sum")).reset_index()
            .sort_values("PLAYS", ascending=False).head(12))
    st.dataframe(load, hide_index=True, use_container_width=True,
                 column_config={"OWNER_REP_NAME": "Rep", "PARTNER_NAME": "Partner",
                                "PLAYS": st.column_config.ProgressColumn("Plays (cap 5)", min_value=0, max_value=int(max(10, load["PLAYS"].max())), format="%d"),
                                "VALUE": st.column_config.NumberColumn("Expected ARR", format="dollar")})

    st.subheader("Partners that need you")
    need = (plays[plays["PARTNER_NEEDS_INTERVENTION"]].groupby("PARTNER_NAME")
            .agg(NRR=("PARTNER_NRR", "first"), AT_RISK=("PARTNER_AT_RISK_SHARE", "first"), PLAYS=("CANDIDATE_ID", "size"))
            .reset_index().sort_values("NRR"))
    if need.empty:
        st.caption("No partner is below the NRR floor or above the at-risk ceiling.")
    for r in need.itertuples():
        st.markdown(f"**{r.PARTNER_NAME}** · NRR {pct(r.NRR)} · {pct(r.AT_RISK)} of ARR at risk · {r.PLAYS} plays")

    st.subheader("Approved this week")
    approved = query("""SELECT p.CREATED_AT, c.ACCOUNT_NAME, p.PLAY_TYPE, p.VALUE_USD, p.STATUS, p.CREATED_BY
                        FROM TRULINE.APP.PLAYS p LEFT JOIN TRULINE.APP.PLAY_CANDIDATES c ON c.CANDIDATE_ID = p.CANDIDATE_ID
                        WHERE c.PAM_ID = ? ORDER BY p.CREATED_AT DESC LIMIT 20""", (pam_id,))
    st.dataframe(approved, hide_index=True, use_container_width=True,
                 column_config={"VALUE_USD": st.column_config.NumberColumn("Value", format="dollar")})
