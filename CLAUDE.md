# Truline Partner Coverage Agent — hackathon project context

Snowflake × Anthropic "Intelligence at Work" hackathon, Fri Oct 23 2026, SVAI Hub, Menlo Park. Solo build.
Data generator context lives in `data_gen/CLAUDE.md` (read it before touching the data).

## Hard constraints (from the participant guide)
- **Submissions due 4:30 PM PT** (form: https://cerebralvalley.ai/e/intelligence-at-work-hackathon/hackathon/submit). Round 1 judging 4:45 PM: ~3 min live demo + 1–2 min Q&A. Top 6 on stage 5:45 PM.
- Repo **must be public**. Demo must show only work built today (keep commit history clean and descriptive).
- **1-minute demo video** required in the submission. Plan: record with Playwright from a script; user adds voice-over.
- Problem statement: Claude + Snowflake surfaces; Snowflake = governed source of truth, Claude = intelligence turning it into decisions/actions; "well beyond a single prompt"; **make governance visible**.
- Banned: basic RAG, **dashboard as the main feature**, edu/mental-health/nutrition/medical chatbots, job screeners, image/personality analyzers, sports coaches.
- Judging: Impact 35% · Demo (works?) 30% · Creativity 25% · Craft with Snowflake & Claude 10% (equal weights in final round).

## Product (decided)
Agent that works for **Truline PAMs** (Partner Account Managers) at a fictional B2B design-software vendor: triages the partner portfolio in Snowflake, picks plays (churn/contraction rescue, credit-burn plays, expansion), delegates them to the right **partner rep**, and produces review-ready documents where **every number is cited** and each reader sees **only data they are entitled to**.
Pitch framing: one governed engine, **autonomy increases as human coverage thins** — one use case per partner coverage model.

| Tier | Coverage | Deliverables |
|---|---|---|
| 1 Dedicated PAM | Top 50 partners by ARR, 1 PAM each | Strategic Account Brief (product-level diagnosis + live web "why now", cited); Partner Business Review pack in two versions (internal / partner-shareable, redacted by role) |
| 2 Shared PAM | Next 250 partners, ~20 per PAM | Weekly Delegation Plan (ranked plays across partners, owner rep, rep load, expected ARR); partners needing intervention; approve → written to PLAYS + AUDIT_LOG |
| 3 Long tail | Bottom 200 partners, no PAM | Monthly partner report ×200 generated in one SQL batch; scoped dataset (secure view + row access policy); stretch: partner agent in Snowflake Intelligence; super-stretch: same agent in Claude via Snowflake-managed MCP |

Optional: synthetic rep notes/tickets + Cortex Search as evidence (only if core works by ~2:30 PM).

### Play rules (decided; thresholds are parameters, tune on 300K)
- **Ranking:** one $ scale = expected ARR impact; tie-break `MONTHS_TO_RENEWAL` asc.
- **Renewal rescue:** `HEALTH_SCORE_CHANGE_3M <= -15`, or `SEAT_UTILIZATION < ~0.60` (proactive right-sizing). Value = `END_ARR × CHURN_PROB_90D`. No risk-band or renewal-window gate (known gap: steady-Critical accounts without a fresh drop are missed).
- **Credits:** Ahead of pace → top-up (value = projected credit shortfall); Below pace & `CONTRACT_MONTH < 8` → adoption; Below pace & `CONTRACT_MONTH >= 8` → commit at risk (value = `COMMIT_ARR_AT_RISK`). Expired-credits play: not used.
- **Expansion:** seat pressure `SEAT_UTILIZATION >= ~0.90` (value = extra seats × unit price); look-alike product gap within industry × segment (value = typical ARR of that product × win rate). Seat→credits play: not used.
- **Delegation:** owner = the account's `PARTNER_REP_ID`; escalate to PAM when $ at stake > threshold, rep exceeds weekly play cap, or partner NRR / at-risk share breaches a limit.
- **As implemented** (`sql/10_core.sql`, thresholds in `CORE.PLAY_PARAMS`): seat expansion also × win rate 0.5 (look-alike 0.25) so all plays share an expected-value scale; look-alike peers = `INDUSTRY_GROUP × SEGMENT` (≥20 peers, ≥50% own it, skip if the family suite is owned); plays below $10K expected value stay out of the weekly plan (→ ~11.4K plays; TP054 = 279, TP001 = 464); escalation threshold $250K, rep cap 5/week, partner NRR floor 95%, at-risk share ceiling 20%; long-tail escalations route to Coverage ops.
- **Planned deviations (approved):** claim checker by construction (LLM writes `{{F#}}` fact placeholders, rendered server-side; reject any other digit); show isolation via the agent in Snowflake Intelligence (caller's rights, unverified); drop `AI_CLASSIFY` unless free-text notes are added; one document generator with an `audience` parameter.

## Snowflake surfaces / features to use
- **Streamlit in Snowflake** = PAM workbench (prefer container runtime). Native components + `config.toml` theme + small inline CSS; no third-party JS components (CSP). Layout: left nav per tier → KPI strip → play cards → document preview with clickable citation chips; `st.status` shows agent steps.
  - **UI decisions (Oct 23):** `st.navigation` with pages **by role** (dedicated PAM → Account brief; shared PAM → Weekly plan; coverage ops → Long tail; everyone → Audit and policies). Identity badge on every page (user, partners visible by policy, data as-of). Per page: ≤4 KPIs → agent output → action. **Agent path = both:** deterministic pipeline (SQL + SPs + `AI_COMPLETE`) shown step by step in `st.status`, plus an "Ask the agent" chat panel calling the Cortex Agent API (hide it if the API can't be called from SiS); the agent is also demoed in Snowflake Intelligence. Citations = inline `F#` badges + Evidence panel (value, semantic-view definition, source view, query ID), fact picked via a selector (native Streamlit can't make inline text clickable). Audit page has a **"catch a made-up number"** button: inject a fabricated number → claim checker blocks and logs it.
- **Cortex Agent** "Truline Coverage Agent": tools = Cortex Analyst (semantic view), web search (name + domain only — internal metrics never leave Snowflake), custom SP tools (`create_play`, `log_action`), optional Cortex Search. Claude as orchestrator if selectable.
- **Semantic view** defining ARR, NRR, GRR, at-risk ARR, burn pace (single governed definitions → citations).
- **AI SQL**: `AI_CLASSIFY` (play type), `AI_COMPLETE` with structured output (briefs/reports), `AI_AGG` (portfolio summaries).
- **Dynamic table** for scored play candidates; **task** for the weekly plan run.
- **Horizon**: row access policies (PAM → their partners; partner → own accounts), masking (`SIM_*`, internal-only fields), query tags + Access History for audit.
- **Claim checker** SP: rejects any number in a generated document not matching a cited query result.
- Shareable docs on a stage, shared via presigned URL.

## Isolation caveat
Streamlit in Snowflake runs with owner's rights by default → row access policies see the owner. Use container runtime + **restricted caller's rights** (Streamlit ≥ 1.53.1, caller grants), or warehouse runtime + `GRANT READ SESSION` to the owner role so policies can use `CURRENT_USER()`. Each persona is a **separate Snowflake user** (e.g. FELIX_PAM, BEN_PAM, PARTNER_Pxxxx); do not fake isolation with an in-app dropdown.

## Unverified — check first (consultation station / account)
Account (checked Oct 23): `ZVB07385`, AWS_US_WEST_2, CLI connection `work_intel`, user has ATTENDEE_ROLE + ACCOUNTADMIN/SECURITYADMIN/USERADMIN, warehouse DEFAULT_WH (XS).
1. ✅ Cortex Agents work; Claude is the orchestrator in an existing agent (`claude-opus-5-5`). Web search: `type: web_search` agent tool is accepted and `ENABLE_CORTEX_WEBSEARCH = TRUE` was set (ACCOUNTADMIN); not yet exercised in a live agent run. No Snowflake Intelligence object exists yet.
2. ❓ Streamlit container runtime + caller's rights: not tested. `SYSTEM_COMPUTE_POOL_CPU` exists (owned by ACCOUNTADMIN).
3. ✅ `AI_COMPLETE('claude-sonnet-4-5', …)` works; cross-region = ANY_REGION. Models up to claude-opus-5-5 / claude-sonnet-5-5 are listed in `SNOWFLAKE.MODELS`.
4. Full 300K generation time in Snowflake (fallback: 50K accounts).
5. Long-tail ARR share is unknown until the 300K run (1K sample has no active long-tail accounts) — lead the impact claim with whichever number is true (accounts/partners covered vs ARR).

## Status
- Done: repo scaffold; Snowflake MCP config (`.mcp.json` + `config/snowflake_mcp_services.yaml`, creds via `SNOWFLAKE_*` env vars, DELETE/DROP/TRUNCATE blocked); generator in `data_gen/`.
- `data_gen/sample_1k/` is gitignored (real company names + synthetic metrics). Regenerate with `python data_gen/run_sample.py`.
- 1K load done in `TRULINE.SYNTH` via `data_gen/run_snowflake.py` (36 s; MONTH is DATE; bridge max error $0.01; views created).
- **300K load with 5K real names done** (`run_snowflake.py work_intel 300000 --real-names`, ~9 min). Real names = `PEOPLE_DATA_LABS.PUBLIC.FREECOMPANYDATASET`, 10001+ employees, name matches website, commercial industries only → `REAL_COMPANIES_SEED`. All 5K real accounts are Enterprise (generator maps 1001+ employees → Enterprise), so total ARR is ~$20.9B and real accounts hold ~$9.4B. NRR 109.3% / GRR 95.6%; bridge max error $0.02. Real active accounts by coverage: Dedicated 3,158 · Shared 1,556 · Long tail 125. Long tail = $627M (~3% of ARR) → lead Tier 3 impact with partners covered, not ARR.
- **Shared core built and tested** (deploy in order with `snow sql -c work_intel -f sql/<file>`; `50_personas.sql` needs ACCOUNTADMIN):
  - `10_core.sql` — `TRULINE.CORE`: dynamic tables `ACCOUNT_CURRENT`, `CONSUMPTION_CURRENT`, `PLAY_CANDIDATES`; `PLAY_PARAMS`, `PLAYS`, `AUDIT_LOG`, `DOC_FACTS`, `DOCUMENTS`, `USER_SCOPE` + `USER_PARTNER_ACCESS`. Personas never read CORE.
  - `20_app.sql` — `TRULINE.APP` secure views (no `SIM_*`) with `RAP_PARTNER_SCOPE` (rows by `CURRENT_USER()` → `USER_SCOPE`), `RAP_OWN_ROWS` (audit/facts/docs), masking `MP_INTERNAL_*` on churn probability, drivers, escalation reason for partner users. **Policies are user-based, not role-based**: `IS_ROLE_IN_SESSION` leaked through secondary roles (ACCOUNTADMIN), so don't reintroduce it. Admin user `USER` has scope ALL.
  - `30_semantic_view.sql` — `APP.TRULINE_COVERAGE` (metrics: total_arr, nrr, grr, at_risk_arr, expected_arr_at_risk, total_consumption_arr, consumption_share, portfolio_burn_pace, total_commit_arr(_at_risk), projected_shortfall, play_count, play_value, product_arr …). Metric names must not equal physical column names (cycle error); no reps→partners relationship (multi-path error).
  - `40_procs.sql` — caller's-rights procs: `APPROVE_PLAYS(array, note)`, `LOG_ACTION`, `BUILD_FACTS(doc_type, subject_id, audience)` (facts from the semantic view, each with metric + query ID), `CHECK_CLAIMS(doc_id, draft)` (rejects any digit not from a `{{F#}}` fact or a fact's entity name; internal facts banned in partner docs), `GENERATE_DOC(doc_type, subject_id, audience, model)` (Claude via `AI_COMPLETE`, deterministic check + Claude label-consistency check, one repair attempt; statuses PASS / PASS_WITH_WARNINGS / FAIL). Doc types: PARTNER (internal|partner), PARTNER_MONTHLY (partner), PAM_PORTFOLIO (internal; subject 'ME' = caller's PAM).
  - `50_personas.sql` — roles `TRULINE_PAM/PARTNER/OPS`; users **FATIMA_HAYES** (dedicated PAM TP001, 1 partner, 6,390 active accts), **NOAH_SHELBY** (shared PAM TP054, 19 partners), **VERTEX_PARTNER** (long-tail partner P0370, 190 accts, masked fields), **COVERAGE_OPS** (all). **Created without passwords — the user sets them in Snowsight.** Test without logging in: `EXECUTE USING POLICY_CONTEXT(CURRENT_ROLE => 'TRULINE_PAM', CURRENT_USER => 'NOAH_SHELBY') AS SELECT …`.
  - Verified: persona row counts and masking; approve skips invisible/duplicate candidates; injected "$4.7M … 12%" → CLAIM_CHECK_FAIL logged; generated docs PASS. Known limit: the label check can flag nitpicks (PASS_WITH_WARNINGS).
- **Streamlit workbench deployed and verified as admin** (`TRULINE.APP.COVERAGE_WORKBENCH`; code in `streamlit/`, deploy with `scripts/deploy_streamlit.sh`, objects + caller grants in `sql/60_streamlit.sql`). Weekly plan (Tier 2) and Audit pages work: KPIs from the semantic view, "Run this week's plan" (agent steps in `st.status` → Claude summary with citation badges + evidence table), play cards in a form → `APPROVE_PLAYS`, "Delegate all rep plays", rep load, partners needing you, injected-number demo → CLAIM_CHECK_FAIL. Account brief / Long tail are placeholders. Open: `https://app.snowflake.com/us-west-2/zvb07385/#/streamlit-apps/TRULINE.APP.COVERAGE_WORKBENCH`.
  - **Verified:** container runtime (`SYSTEM$ST_CONTAINER_RUNTIME_PY3_11`, `SYSTEM_COMPUTE_POOL_CPU`) + **restricted caller's rights** (`st.connection("snowflake-callers-rights")`; audit rows show the viewer's user/role). Persona isolation inside the app not yet tested with a real persona login (needs passwords).
  - **Gotchas:** packages need `ARTIFACT_REPOSITORIES = (snowflake.snowpark.pypi_shared_repository)` + `GRANT DATABASE ROLE SNOWFLAKE.PYPI_REPOSITORY_USER` (no PyPI egress); set it with ALTER after CREATE (CREATE alone didn't take). Caller connection uses **qmark `?` binding**; no binds inside `SEMANTIC_VIEW(...)` (inline validated IDs). Restricted sessions can't call `SNOWFLAKE.CORTEX.*` (no caller grants on shared objects) → owner's-rights gateway `APP.LLM_COMPLETE(model, prompt)` (approved Claude models only); facts are still built with caller's rights. Escape `$` in markdown (LaTeX). Don't name the folder `pages/` (auto-MPA bypasses `st.navigation`) → `views/`. Checkboxes go in `st.form` (each tick reruns + jumps scroll). First start of the compute pool takes ~5 min.
  - The user separately created an allow-all EAI via Snowsight Cortex Code (`TRULINE.APP.ALLOW_ALL_NETWORK_RULE`, 0.0.0.0/0); not used by the app.
- **Cortex Agent built** (`sql/70_agent.sql`): `TRULINE.APP.TRULINE_COVERAGE_AGENT` (Claude orchestration `claude-sonnet-4-5`), tools: `CoverageMetrics` (Analyst on the semantic view), `WebSearch` (name/domain only, per instructions), `CitedDocument` (→ `GENERATE_DOC`), `ApprovePlays` (→ `AGENT_APPROVE_PLAYS`, comma-separated IDs; agent tools can't take OBJECT args), `LogAction` (→ `AGENT_LOG_ACTION`), `data_to_chart`. Added to the **Snowflake Intelligence** object `SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT` (USAGE granted to persona roles). Verified via REST: semantic-view answers with candidate IDs; web search with citations ("why now" for Fidelity). Semantic view gained `plays.partner_needs_intervention` + `rep_over_cap` (CREATE OR REPLACE drops grants → re-grant SELECT and CALLER SELECT).
  - **Ask the agent** page (`streamlit/views/agent.py`): POSTs to the agent `:run` REST endpoint with the caller's-rights session token (`conn()._instance.rest.token`), streams status/tool events into `st.status`, renders text + tables. Needed `GRANT CALLER USAGE ON AGENT … TO ROLE ATTENDEE_ROLE`. Verified as admin; answers take 30–90 s.
- **Next:** Tier 1 brief page (CitedDocument + web search), Tier 3 batch page, persona login test, README + video. Old note: run notebook at 1K → checks → 300K → app views; run the 3 checks above; then build in this order: shared core (semantic view, policies, candidates DT, PLAYS/AUDIT_LOG, claim checker) → Tier 2 → Tier 1 (web search) → Tier 3 batch → stretch partner agent (only if all works by ~3:00 PM) → README + video script by 3:30 PM → submit by 4:15 PM.

## User working preferences
- Flag uncertainty; say "I don't know" rather than guess. Cite sources for factual claims; separate fact from opinion; state confidence.
- Ask up to 3 clarifying questions when ambiguous. Ask permission before running code for math/stats where it reduces uncertainty.
- Token-efficient; write code, never generate data rows with the LLM.
- Truline is fictional: do not use Autodesk names. Keep `SIM_*` columns out of the app/demo. Never commit secrets.
