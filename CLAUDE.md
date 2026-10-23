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
- **Planned deviations (approved):** claim checker by construction (LLM writes `{{F#}}` fact placeholders, rendered server-side; reject any other digit); show isolation via the agent in Snowflake Intelligence (caller's rights, unverified); drop `AI_CLASSIFY` unless free-text notes are added; one document generator with an `audience` parameter.

## Snowflake surfaces / features to use
- **Streamlit in Snowflake** = PAM workbench (prefer container runtime). Native components + `config.toml` theme + small inline CSS; no third-party JS components (CSP). Layout: left nav per tier → KPI strip → play cards → document preview with clickable citation chips; `st.status` shows agent steps.
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
- **Next:** run notebook at 1K → checks → 300K → app views; run the 3 checks above; then build in this order: shared core (semantic view, policies, candidates DT, PLAYS/AUDIT_LOG, claim checker) → Tier 2 → Tier 1 (web search) → Tier 3 batch → stretch partner agent (only if all works by ~3:00 PM) → README + video script by 3:30 PM → submit by 4:15 PM.

## User working preferences
- Flag uncertainty; say "I don't know" rather than guess. Cite sources for factual claims; separate fact from opinion; state confidence.
- Ask up to 3 clarifying questions when ambiguous. Ask permission before running code for math/stats where it reduces uncertainty.
- Token-efficient; write code, never generate data rows with the LLM.
- Truline is fictional: do not use Autodesk names. Keep `SIM_*` columns out of the app/demo. Never commit secrets.
