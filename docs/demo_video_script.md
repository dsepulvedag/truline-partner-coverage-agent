# Demo video script (60 s): Truline Partner Coverage Agent

Target 57 s, ~150 spoken words. Bracketed values like `[weekly plan value]` are read off the screen at recording time; don't say a number the app isn't showing.
Status: **BUILT** = exists in Snowflake now. **PLANNED** = must be built before recording (or recorded through the Snowsight fallback in the notes).

| # | Time | On screen | Voice-over | Action / click | Status |
|---|---|---|---|---|---|
| 1 | 0:00–0:07 | Title card, then a 3-band coverage map: Top 50 = dedicated PAM · Next 250 = shared PAM · Bottom 200 = no PAM | "Truline sells through five hundred partners. Fifty get a dedicated manager, two hundred fifty share one, two hundred get nobody." | Static, bands appear one by one | PLANNED (title card) |
| 2 | 0:07–0:12 | Workbench home in Streamlit in Snowflake; caption: *Semantic view · Dynamic table · Row access policies* | "One governed engine on Snowflake, Claude doing the work, more autonomy as coverage thins." | Left nav by role is visible | PLANNED (UI) on BUILT data |
| 3 | 0:12–0:25 | **Hero.** Weekly plan as NOAH_SHELBY: identity badge "19 partners", KPI strip, ranked play cards (play type, owner rep, expected ARR, escalation badge); `st.status` shows the agent steps; caption: *Dynamic table PLAY_CANDIDATES* | "Noah covers nineteen partners. The agent ranks this week's plays by expected ARR, `[weekly plan value]`, routes each to the owner rep, and escalates the big ones. One click approves and logs it." | Expand `st.status` → scroll the cards → tick top plays → **Approve** → toast "N plays written to PLAYS + AUDIT_LOG" | BUILT: `PLAY_CANDIDATES`, `APPROVE_PLAYS`, routing/escalation · PLANNED: page |
| 4 | 0:25–0:35 | Account brief as FATIMA_HAYES (badge "1 partner"): brief with `F#` chips, Evidence panel (value, metric definition, source view, query ID), "Why now" with web links; toggle **Internal / Partner-shareable**; caption: *Cortex AI_COMPLETE · Claude* | "For Fatima's top partner, Claude writes a brief where every number cites the semantic view, plus a live why-now from the web. One toggle makes the partner-shareable version." | Pick a fact chip → Evidence panel opens → toggle to Partner version (internal facts disappear) | BUILT: `GENERATE_DOC` (PARTNER internal + partner), `BUILD_FACTS` · PLANNED: page, web search |
| 5 | 0:35–0:41 | Long tail page as COVERAGE_OPS: table of 200 monthly partner reports, all claim-checked; open one | "The two hundred uncovered partners get monthly reports from one SQL batch." | Sort by status → open one report | BUILT: `GENERATE_DOC` (PARTNER_MONTHLY) · PLANNED: batch, page |
| 6 | 0:41–0:51 | Split screen, same app, three logins: Noah "19 partners", Fatima "1", VERTEX_PARTNER "1" with churn probability blank and drivers "\*\*\* internal \*\*\*". Then Audit page: **Catch a made-up number** → red FAIL "uncited number: $4.7M" → new AUDIT_LOG row | "Three Snowflake users, three different views, enforced by row access and masking policies. And a made-up four point seven million? The claim checker blocks it and logs it." | Cut between the three badges → Audit page → click the button → highlight the audit row | BUILT: policies, `MY_SCOPE`, persona users, `CHECK_CLAIMS` + AUDIT_LOG · PLANNED: pages, button |
| 7 | 0:51–0:57 | Close card: "500 of 500 partners covered · every number cited · every action audited"; logos Snowflake × Claude | "Every partner covered, every number sourced, every action audited." | Static | PLANNED (card) |

Feature names (spoken or as captions): Streamlit in Snowflake (2–6), dynamic table (3), semantic view (2, 4), Cortex AI_COMPLETE with Claude (4), row access + masking policies (6). If the **Cortex Agent** "Ask the agent" panel works, swap shot 4's "plus a live why-now from the web" for "and the Cortex Agent adds a live why-now" and show the chat panel for 2 s.

## Recording notes

- **Method:** Playwright script, one browser context per persona (each is a real Snowflake user; no in-app persona switcher). Record each shot as its own clip (`recordVideo`), splice in the editor, user adds voice-over last. Read the VO aloud once against the clips and trim to the picture.
- **Logins:** persona users have no passwords yet; the user sets them in Snowsight and signs in once per context, then saves `storageState` outside the repo. Never put passwords in the script or commit them.
- **Prepare before recording:**
  - NOAH_SHELBY (TP054): Weekly plan with **unapproved** candidates. `APPROVE_PLAYS` skips candidates already approved this week and DELETE is blocked, so rehearse on lower-ranked plays and keep the top cards for the take. Note `[weekly plan value]` and the play count.
  - FATIMA_HAYES (TP001, 1 partner): pre-generate the internal and partner briefs (`GENERATE_DOC` runs two Claude calls, so don't wait on camera); pick the fact chip to click.
  - VERTEX_PARTNER (P0370, Vertex Digital Consulting): accounts page open, with a masked column in view.
  - COVERAGE_OPS: Tier 3 batch already run (200 rows); Audit page loaded with the button ready.
- **Fallback for PLANNED UI:** record BUILT parts in Snowsight worksheets instead: `SELECT * FROM TRULINE.APP.MY_SCOPE` as each persona (shot 6); `CALL TRULINE.APP.APPROVE_PLAYS(...)` and the AUDIT_LOG row (shot 3); `CALL TRULINE.APP.CHECK_CLAIMS(<doc_id>, '... $4.7M ...')` returning FAIL (shot 6).
- **30-second cut** (if time runs short): shot 1 trimmed to 0:00–0:05 ("500 partners; the last 200 get nobody") → shot 3 (0:05–0:17) → shot 6 (0:17–0:27) → shot 7 (0:27–0:30). Drop shots 2, 4 and 5.
