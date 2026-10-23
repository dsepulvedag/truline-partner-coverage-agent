# Truline synthetic data — project context

Hackathon project (Snowflake hackathon sponsored by Anthropic, Oct 23 2026). The app helps a B2B SaaS vendor and its reseller partners spot customer health, churn risk and expansion opportunities. This folder holds the **synthetic data generator** that feeds it. Everything about Truline is fictional; 5K customer accounts use real company names so the app can research them (web / Clay) by `DOMAIN`.

## Decisions already made (don't revisit unless asked)
- **Vendor:** "Truline", fictional design-software company (do NOT use Autodesk names or anything Autodesk-specific). 15 fictional per-seat products in 4 families + "Truline Cloud Credits".
- **Scale:** 300K customer accounts (5K real names, 295K fictional), 500 fictional reseller partners, 36 months (Oct 2023 – Sep 2026).
- **Real names:** largest companies in design-heavy industries from the People Data Labs free company dataset on Snowflake Marketplace (notebook cells 2a/2b; table/column names unverified). Fictional accounts get `.example` domains so they never resolve — only research `IS_REAL_COMPANY = TRUE`.
- **Grain:** usage per account × product × month; ARR bridge per account × month; health score monthly history (score, band, 2 reason codes, 90-day churn probability).
- **ARR:** seat ARR = seats × unit price (list − segment discount, ×1.2 monthly term, +3% uplift at renewal).
- **Consumption:** prepaid annual credit commitment = consumption ARR; usage draws it down; overage billed at list ($1/credit) = revenue, not ARR; unused credits expire at renewal; next commit re-sized on trailing usage; mid-year top-ups when burning ahead of pace. Seat accounts migrate (some/all products) to credits at renewal, rising over time (more in Enterprise); 25% of new logos in the last 18 months start on credits.
- **ARR bridge identity:** START + NEW + EXPANSION − CONTRACTION − CHURN − MIGRATED_OUT + MIGRATED_IN = END (reconciles to cents).
- **Coverage (snapshot only, labels only — must not change outcomes):** top 50 partners by active ARR → dedicated Truline PAM; next 250 → shared PAM (~1 per 20, within region); rest → long tail, no PAM. Partner reps own customer accounts: generalist "Account Manager" at small partners; segment specialists at larger ones (Inside Sales ≤250 SMB, AE ≤40 Mid-Market, Strategic AM ≤10 Enterprise), books balanced by ARR. Coverage uses its own RNG stream so all other outputs stay identical.
- **Where it runs:** Snowflake Notebook (Warehouse Runtime, Python 3.9 → keep code 3.9-compatible; numpy + pandas only). Tables written with `session.write_pandas`; date columns are Python `date` objects → parquet date32 → DATE.

## Files
- `truline_gen.py` — the generator (single source of truth). `generate(sink, real_df=None, **overrides)`; `csv_sink(folder)` locally, `snowflake_sink(session, db, schema)` in Snowflake.
- `build_notebook.py` — rebuilds `truline_snowflake_notebook.ipynb` from `truline_gen.py` (embeds it as cell 3). Re-run after any generator change.
- `truline_snowflake_notebook.ipynb` — import into Snowsight (Projects » Notebooks » ▾ next to + Notebook » Import .ipynb). Cells: 1 setup (N_ACCOUNTS=1_000 smoke test → then 300_000), 2a/2b optional real names, 3 generator code, 4 generate, 5 checks, 6 app views.
- `validate.py` — `python validate.py <folder> <n_accounts>` runs locally and prints calibration metrics; `fit(folder)` refits the churn-probability curve.
- `run_sample.py` — regenerates `sample_1k/` (1K accounts, 17 real names).
- `sample_1k/` — 9 CSVs, one per table.

## Tables (schema TRULINE.SYNTH)
PRODUCTS (16) · PARTNERS (500; COVERAGE_MODEL, PAM_ID, CURRENT_MANAGED_ARR, PARTNER_ARR_RANK) · TRULINE_PAMS (~64) · PARTNER_REPS (~2,900 at 300K) · ACCOUNTS (300K; PARTNER_ID, PARTNER_REP_ID, BILLING_MODEL, CURRENT_* fields) · SUBSCRIPTIONS · SUBSCRIPTION_MONTHLY (~12.6M; product rows + one CREDITS row per consumption account so ARR sums to account END_ARR) · ACCOUNT_MONTHLY (~8.5M; bridge, SEAT_ARR, CONSUMPTION_ARR, usage, health) · CONSUMPTION_MONTHLY (~440K; commit, burn pace/status, overage, top-ups, expired).
Views: V_ACCOUNT_LATEST, V_OUTREACH_QUEUE, V_CONSUMPTION_WATCH, V_PARTNER_SCORECARD, V_REP_BOOK, V_PAM_PORTFOLIO.
`SIM_*` columns (SIM_TRAJECTORY, SIM_PARTNER_QUALITY) are hidden ground truth — keep them out of the app/demo.

## Calibration (20K-account run; synthetic, illustrative)
NRR ~108%, GRR ~95%; logo churn SMB ~7.5%/yr, Enterprise ~1%; consumption ~21% of ARR (Enterprise ~30% of accounts on credits, MM ~21%, SMB ~11%); credit accounts NRR ~113% vs seats ~108%; migration uplift ~+5%; overage ~4% and expired credits ~4% of consumption ARR; health-score AUC ~0.76 within renewal windows (Critical ~20% churn in 90 days vs Healthy ~2%); bands ~64% Healthy / 20% Watch / 10% At Risk / 6% Critical. Full 300K run: ~49 s compute, ~2.5 GB peak memory locally.

Benchmarks used to sanity-check: SaaS Capital 2025 B2B retention survey (median NRR 101%, GRR 91%); public design-software revenue mix by product family and region (used only as unnamed tuning weights).

## Status / next steps
- Generator, sample and notebook are done and tested locally (plus a mocked Snowflake session). **Not yet run in a real Snowflake account.**
- Next: run the notebook in Snowflake (1K smoke test → 300K), confirm `MONTH` columns are DATE and the bridge check is ~0, then build the app on the views.
- If the 300K run hits memory limits: lower `CHUNK` (e.g. `generate(..., CHUNK=10_000)`) or use a Medium / Snowpark-optimized warehouse.
- Possible alternative to the notebook: run `truline_gen.py` from this machine with Snowpark + the user's own connection config (`snowflake_sink(session, "TRULINE", "SYNTH")`). The user enters credentials themselves.

## Working preferences (user)
- Token-efficient: write code, never generate data rows with the LLM; avoid long explanations.
- Flag uncertainty and unverified assumptions; cite sources for factual claims; separate facts from opinions.
- Ask before running code only when the user hasn't already asked for it.
