# Truline Partner Coverage Agent

**Snowflake × Anthropic "Intelligence at Work" hackathon, Oct 23 2026.** Built today, solo.

Truline (fictional) sells design software through 500 reseller partners. Only the top 50 get a dedicated Partner Account Manager (PAM); the next 250 share one PAM per ~20; the bottom 200 get nobody. This project is **one governed engine whose autonomy grows as human coverage thins**:

| Coverage | Who | What the agent does |
|---|---|---|
| Dedicated PAM (top 50) | 1 PAM per partner | Strategic brief + partner-shareable business review side by side, every number cited; "why now" from the web for real customer names |
| Shared PAM (next 250) | 1 PAM per ~20 partners | **Weekly delegation plan**: ranks plays across all partners, assigns the owner rep, escalates what needs the PAM, approve → written to `PLAYS` + `AUDIT_LOG` |
| Long tail (bottom 200) | nobody | Monthly partner report written by Claude from governed data; partner users see only their own data |

Snowflake is the governed source of truth; Claude turns it into decisions and actions. **Every number in a generated document is cited, and every reader sees only what they are entitled to.**

## How it works

```
SYNTH tables (300K accounts, 5K real company names, 36 months)
   │
CORE  dynamic tables: ACCOUNT_CURRENT, CONSUMPTION_CURRENT, PLAY_CANDIDATES (rules in PLAY_PARAMS)
   │  PLAYS, AUDIT_LOG, DOC_FACTS, DOCUMENTS, USER_SCOPE
   │
APP   secure views + row access policy (by CURRENT_USER) + masking (internal fields for partners)
   │  semantic view TRULINE_COVERAGE (ARR, NRR, GRR, at-risk ARR, burn pace, plays …)
   │  caller's-rights procedures: APPROVE_PLAYS, BUILD_FACTS, CHECK_CLAIMS, GENERATE_DOC
   │
   ├─ Cortex Agent "Truline Coverage Agent" (Claude): semantic view · web search · cited documents · approve · log
   │     └─ in Snowflake Intelligence
   └─ Streamlit in Snowflake workbench (container runtime, restricted caller's rights)
         Weekly plan · Account brief · Long tail · Ask the agent · Audit and policies
```

**Claim checker.** `BUILD_FACTS` computes numbered facts (F1…Fn) from the semantic view, each with its governed metric and source query ID. Claude (`AI_COMPLETE`) writes the document using only `{{F#}}` placeholders. `CHECK_CLAIMS` rejects any number that is not a cited fact (and internal-only facts in partner documents), then a second Claude pass checks each fact is described faithfully; one repair attempt, then PASS / PASS_WITH_WARNINGS / FAIL. Every step is logged.

**Governance you can see.**
- Each persona is a real Snowflake user (`NOAH_SHELBY` shared PAM, `FATIMA_HAYES` dedicated PAM, `VERTEX_PARTNER` long-tail partner, `COVERAGE_OPS`). The same app and agent show each of them different rows; partner users get churn probability, risk drivers and escalation reasons masked.
- The Streamlit app uses **restricted caller's rights**, so policies apply in the UI, and the agent page calls the Cortex Agent with the viewer's token.
- Web search sends company name and domain only; internal metrics never leave Snowflake.
- Audit page: actions, claim checks, and a "catch a made-up number" button that injects `$4.7M` into a draft and shows it blocked.

## Snowflake and Claude features used

Semantic view · Cortex Analyst (via agent) · Cortex Agent with Claude orchestration, web search and custom procedure tools · Snowflake Intelligence · `AI_COMPLETE` with Claude · dynamic tables · row access and masking policies · secure views · caller's-rights procedures · Streamlit in Snowflake (container runtime, restricted caller's rights, Snowflake PyPI mirror) · query tags.

## Repo

| Path | What |
|---|---|
| `data_gen/` | Synthetic data generator (Snowflake notebook + `run_snowflake.py`); real names from the People Data Labs free company dataset (Marketplace) |
| `sql/00_account.sql` … `70_agent.sql` | Account settings, core, governed app layer, semantic view, procedures, personas, Streamlit, agent (run in order) |
| `sql/playground.sql` | Worksheet to try everything in Snowsight |
| `streamlit/` | Workbench app; deploy with `scripts/deploy_streamlit.sh` |
| `docs/demo_video_script.md` | 1-minute demo script |

## Run it

0. Account settings (ACCOUNTADMIN, once): `snow sql -c <connection> -f sql/00_account.sql` (cross-region inference for Claude, Cortex web search).
1. Generate data: `uv run --python 3.11 --with "snowflake-snowpark-python[pandas]" --with numpy python data_gen/run_snowflake.py <connection> 300000 --real-names` (needs the People Data Labs listing as `PEOPLE_DATA_LABS`).
2. `snow sql -c <connection> -f sql/10_core.sql`, then `20_app`, `30_semantic_view`, `40_procs`, `50_personas` (ACCOUNTADMIN), `70_agent`.
3. `scripts/deploy_streamlit.sh <connection>` (runs `sql/60_streamlit.sql`).
4. Persona users are created without passwords; set them in Snowsight to log in as a persona.

## Notes

- All Truline data is synthetic. 5,000 accounts carry real company names and domains so web research works; their metrics are invented.
- Truline is fictional and not affiliated with any real software vendor.
