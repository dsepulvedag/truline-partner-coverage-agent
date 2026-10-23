# Demo video script (60 s): Truline Partner Coverage Agent

Target 57 s, ~150 spoken words (~155 wpm). Numbers in the voice-over are what the deployed app shows today (Noah: 279 plays, $24.3M expected ARR; long tail: 200 partners, ~21.7K customers, $627M ARR). Re-check them on screen before recording.
**BUILT** = works in the deployed app. **TODO** = make before recording.

| # | Time | On screen | Voice-over | Action / click | Caption | Status |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:06 | Coverage map card: Top 50 = dedicated PAM · Next 250 = shared PAM · Bottom 200 = no PAM | "Truline sells through 500 partners. Fifty get a dedicated manager, 250 share one, and 200 get nobody." | Bands appear one by one | — | TODO (card) |
| 2 | 0:06–0:10 | Workbench in Streamlit in Snowflake: role-based nav + identity badge | "One governed engine on Snowflake, with Claude doing more as coverage thins." | Hold on the nav and badge | *Streamlit in Snowflake · caller's rights* | BUILT |
| 3 | 0:10–0:22 | **Hero.** Weekly plan as NOAH_SHELBY: badge "19 of 500 partners", KPIs, `st.status` agent steps, ranked play cards with owner rep and escalation badges → tick → **Approve ticked plays** → toast | "Noah covers 19 partners. The agent ranks 279 plays worth $24.3 million in expected ARR, routes each to the owner rep, escalates the big ones, and one click approves and logs them." | Expand the (pre-run) status → scroll cards → tick 2 plays from #5 down → Approve → toast "N plays written to PLAYS and AUDIT_LOG" | *Semantic view · Dynamic table* | BUILT |
| 4 | 0:22–0:30 | Account brief as FATIMA_HAYES: internal brief and partner version side by side, `F#` citation badges, Evidence table (value, governed metric, query ID), "Withheld from the partner version by policy" | "For Fatima's top partner, Claude writes the internal brief and the partner version. Every number cites the semantic view; internal facts never reach the partner." | Scroll both versions (pre-generated) → open Evidence | *AI_COMPLETE · Claude · claim checker* | BUILT |
| 5 | 0:30–0:37 | Why now: per-account **Signal** (Expansion / Headwind) with dated sources, then **Play alignment** / **Opportunity** and **Recommendation** | "Then it checks the news against our plays: growth says push, headwinds say pull back." | Scroll the (pre-run) answer; pause on one Aligned and one Headwind/right-size verdict | *Cortex Agent · web search (name + domain only)* | BUILT |
| 6 | 0:37–0:42 | Long tail: KPIs "200 partners · ~21.7K customers · $627M", one partner's monthly report with claim-check badge | "The 200 partners nobody covers get a monthly report, written by Claude and claim-checked." | Scroll the (pre-generated) report for Vertex Digital Consulting (P0370) | — | BUILT (one sample report) |
| 7 | 0:42–0:52 | Three identity badges: Noah "19 of 500", Fatima "1 of 500", VERTEX_PARTNER "1 of 500" → Audit page: **Inject and re-check** → "Blocked: … not backed by a cited fact" → CLAIM_CHECK_FAIL row | "Each persona is a real Snowflake user, so policies decide what they see. A made-up 4.7 million? Blocked and logged." | Cut between the three badges → Audit → click **Inject and re-check** → highlight the log row | *Row access + masking policies · audit log* | BUILT (persona logins need passwords) |
| 8 | 0:52–0:57 | Close card: "One engine for all 500 partners · every number cited · every action audited" + Snowflake × Claude | "Every number sourced, every action audited, every partner in reach." | Static | — | TODO (card) |

Optional 2 s insert (replace part of shot 2 if time allows): **Ask the agent** page, or the same agent in Snowflake Intelligence, answering "Which of my partners need me this week?" as the viewer.

## Recording notes

- **Method:** Playwright, one browser context per persona (each is a real Snowflake user; there is no in-app persona switcher). Record each shot as its own clip (`recordVideo`), splice, then add the voice-over and trim to the picture. Cards (shots 1 and 8) can be a small local HTML page recorded the same way.
- **Logins:** set passwords for NOAH_SHELBY, FATIMA_HAYES and VERTEX_PARTNER in Snowsight (Admin → Users & roles), sign in once per context and save `storageState` outside the repo. Never put passwords in the script or commit them. App URL: Snowsight → Projects → Streamlit → *Truline coverage*.
- **Pre-run every Claude step** (never wait on camera); results stay in the page session, so record in the same browser session right after:
  - Weekly plan "Run this week's plan" (~40 s).
  - Account brief "Generate brief and partner review" (~1.5 min for both versions).
  - "Find why-now signals" (~60–90 s). Keystone (P0014) gave a good mix last time: Aligned (Pfister Faucets), Unclear (FCA US), expansion opportunity (United Rentals), right-size (Mariano's).
  - Long tail "Generate this month's report" for P0370 (~30 s).
- **Approvals can't be undone** (`APPROVE_PLAYS` skips plays already approved this week; deletes are blocked). Noah's plays #1–#4 are already approved from testing, so tick plays from #5 down, and don't rehearse on the ones you'll use in the take.
- **What each persona sees:** Noah → Weekly plan + Ask the agent (19 partners). Fatima → Account brief + Ask the agent (1 partner, Keystone). VERTEX_PARTNER → Long tail + Ask the agent (own partner only; churn probability, risk drivers and escalation reasons are masked, which shows up in agent answers, not on a page). Admin/COVERAGE_OPS → all pages.
- **Fallback if persona logins aren't ready:** run in a Snowsight worksheet, as admin:
  `EXECUTE USING POLICY_CONTEXT(CURRENT_ROLE => 'TRULINE_PAM', CURRENT_USER => 'NOAH_SHELBY') AS SELECT COUNT(*) FROM TRULINE.APP.PARTNERS;`
  and the same for FATIMA_HAYES and VERTEX_PARTNER (role `TRULINE_PARTNER`), which return 19 / 1 / 1. The made-up-number demo works as admin on the Audit page.
- **30-second cut:** shot 1 (0:00–0:05, "500 partners; 200 get nobody") → shot 3 (0:05–0:17) → shot 7 (0:17–0:27) → shot 8 (0:27–0:30).
