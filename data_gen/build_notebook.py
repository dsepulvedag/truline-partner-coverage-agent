import json
import os
HERE = os.path.dirname(os.path.abspath(__file__))

gen_src = open(os.path.join(HERE, "truline_gen.py")).read()

md_intro = """# Truline synthetic data generator

Builds a fictional B2B design-software company (**Truline**) in this schema: 15 seat-based products plus **Truline Cloud Credits** (prepaid consumption), 500 fictional reseller partners, 300K customer accounts (5K with real company names; every metric about them is synthetic), and 36 months (Oct 2023 – Sep 2026) of usage, ARR movements, credit burn and an illustrative health score.

**Consumption model:** customers prepay an annual credit commitment (that commitment is their consumption ARR); usage draws it down; usage beyond it is billed as overage at list price (revenue, not ARR); unused credits expire at renewal, when the next commitment is re-sized on actual usage. A growing share of seat customers migrate some or all products to credits at renewal, and some newer customers start on credits. ARR bridge: START + NEW + EXPANSION − CONTRACTION − CHURN − MIGRATED_OUT + MIGRATED_IN = END.

**Coverage (current snapshot, labels only):** the top 50 partners by active ARR have a dedicated Truline Partner Account Manager (PAM); the next 250 share a PAM (~1 per 20 partners, within region); the rest are long tail with no PAM (`TRULINE_PAMS`, `PARTNERS.PAM_ID`). Each customer account is owned by a partner rep (`PARTNER_REPS`, `ACCOUNTS.PARTNER_REP_ID`); small partners have generalist Account Managers, larger ones have segment specialists sized by book.

**Run order**
1. **Setup** – creates `TRULINE.SYNTH`. Leave `N_ACCOUNTS = 1_000` for a smoke test first.
2. **Real company names (optional)** – only if you got the People Data Labs free company dataset from Snowflake Marketplace. Otherwise skip; all accounts become fictional and you can rerun later.
3. **Generator code** – just run it (defines functions).
4. **Generate** – writes the tables. ~1K accounts takes seconds; 300K takes several minutes.
5. **Checks** – row counts, column types, ARR bridge, retention, consumption mix, risk bands.
6. **App views** – account 360, outreach queue, consumption watch, partner scorecard, rep book, PAM portfolio.

Then set `N_ACCOUNTS = 300_000` in Setup and rerun cells 1, 4, 5, 6 (cell 2 only if using real names).

If an import fails, add `numpy` and `pandas` from the notebook's **Packages** menu."""

setup = '''# 1) SETUP
from snowflake.snowpark.context import get_active_session
session = get_active_session()

DB, SCHEMA = "TRULINE", "SYNTH"
session.sql(f"CREATE DATABASE IF NOT EXISTS {DB}").collect()
session.sql(f"CREATE SCHEMA IF NOT EXISTS {DB}.{SCHEMA}").collect()
session.sql(f"USE SCHEMA {DB}.{SCHEMA}").collect()

N_ACCOUNTS = 1_000          # smoke test first; then 300_000
N_REAL = round(N_ACCOUNTS * 5_000 / 300_000)   # 5,000 real names at full scale
print(N_ACCOUNTS, "accounts,", N_REAL, "with real names")'''

real_md = """## 2) Real company names (optional)
Run **2a** to find the listing's table and columns, adjust `PDL_TABLE` and the column names in **2b** if they differ, then run **2b**. It keeps the largest companies (any commercial industry) whose name matches their website. Skip both if you don't have the listing."""

real_a = '''# 2a) Explore the People Data Labs listing (edit LISTING_DB to the name you chose when you clicked "Get")
LISTING_DB = "PEOPLE_DATA_LABS"
session.sql(f"SHOW TABLES IN DATABASE {LISTING_DB}").show()
# After you see the table name, set PDL_TABLE and peek at columns and industry values:
PDL_TABLE = f"{LISTING_DB}.PUBLIC.FREECOMPANYDATASET"   # verified Oct 23 2026; adjust if 2a shows otherwise
session.sql(f"SELECT * FROM {PDL_TABLE} LIMIT 5").show()
session.sql(f"SELECT industry, COUNT(*) AS n FROM {PDL_TABLE} GROUP BY 1 ORDER BY 2 DESC LIMIT 60").show(60)'''

real_b = '''# 2b) Pick 5,000 large, real companies (any commercial industry) -> REAL_COMPANIES_SEED
# PDL sizes are self-reported, so keep rows whose name matches the website, with complete profiles,
# no platform pages / sub-sites, and no government, education, religious or non-profit bodies.
NON_COMMERCIAL = ("government administration", "judiciary", "law enforcement", "military", "legislative office",
                  "political organization", "religious institutions", "civic & social organization",
                  "non-profit organization management", "philanthropy", "fund-raising", "think tanks",
                  "primary/secondary education", "higher education", "education management",
                  "international affairs", "public policy", "gambling & casinos", "tobacco",
                  "individual & family services")
PLATFORMS = ("facebook", "instagram", "linkedin", "youtube", "twitter", "wikipedia", "fiverr", "google",
             "linktr", "medium", "github", "wordpress", "blogspot", "wix")
sql_list = lambda xs: ", ".join("'" + x + "'" for x in xs)
session.sql(f"""
CREATE OR REPLACE TABLE REAL_COMPANIES_SEED AS
WITH c AS (
  SELECT INITCAP(name) AS NAME, industry AS INDUSTRY, size AS SIZE_BAND, country AS COUNTRY,
         SPLIT_PART(REGEXP_REPLACE(LOWER(TRIM(website)), '^(https?://)?(www[.])?', ''), '/', 1) AS DOMAIN,
         REGEXP_REPLACE(LOWER(name), '[^a-z0-9]', '') AS NM,
         CASE size WHEN '10001+' THEN 1 WHEN '5001-10000' THEN 2 ELSE 3 END AS SIZE_RANK,
         IFF(founded IS NOT NULL, 1, 0) + IFF(linkedin_url IS NOT NULL, 1, 0) + IFF(locality IS NOT NULL, 1, 0) AS COMPLETENESS
  FROM {PDL_TABLE}
  WHERE name IS NOT NULL AND website IS NOT NULL AND industry IS NOT NULL AND country IS NOT NULL
    AND size IN ('10001+', '5001-10000', '1001-5000')
    AND industry NOT IN ({sql_list(NON_COMMERCIAL)})),
v AS (
  SELECT c.*, SPLIT_PART(DOMAIN, '.', 1) AS STEM, ARRAY_SIZE(SPLIT(DOMAIN, '.')) AS LABELS FROM c
  WHERE REGEXP_LIKE(DOMAIN, '^[a-z0-9-]+([.][a-z0-9-]+)*[.][a-z]{{2,}}$')
    AND NOT REGEXP_LIKE(DOMAIN, '.*[.](gov|mil|edu)([.][a-z]{{2}})?$'))
SELECT NAME, DOMAIN, INDUSTRY, SIZE_BAND, COUNTRY
FROM v
WHERE LENGTH(STEM) >= 3 AND LENGTH(NM) >= 3 AND LENGTH(NAME) <= 40
  AND (NM = STEM OR STARTSWITH(NM, STEM) OR STARTSWITH(STEM, NM))
  AND STEM NOT IN ({sql_list(PLATFORMS)})
  AND (LABELS = 2 OR (LABELS = 3 AND SPLIT_PART(DOMAIN, '.', 2) IN ('co', 'com', 'net', 'org')))
QUALIFY ROW_NUMBER() OVER (PARTITION BY DOMAIN ORDER BY SIZE_RANK, LENGTH(NAME)) = 1
    AND ROW_NUMBER() OVER (PARTITION BY LOWER(NAME) ORDER BY SIZE_RANK, LENGTH(DOMAIN)) = 1
ORDER BY SIZE_RANK, COMPLETENESS DESC, HASH(DOMAIN)
LIMIT 5000
""").collect()
print(session.table("REAL_COMPANIES_SEED").count(), "real companies staged")'''

run = '''# 4) GENERATE (writes PRODUCTS, PARTNERS, TRULINE_PAMS, PARTNER_REPS, ACCOUNTS, SUBSCRIPTIONS,
#    SUBSCRIPTION_MONTHLY, ACCOUNT_MONTHLY, CONSUMPTION_MONTHLY)
import time
try:
    real_df = session.table("REAL_COMPANIES_SEED").to_pandas()
except Exception:
    real_df = None
    print("No REAL_COMPANIES_SEED table - all accounts will be fictional.")
t0 = time.time()
generate(snowflake_sink(session, DB, SCHEMA), real_df=real_df, N_ACCOUNTS=N_ACCOUNTS, N_REAL=N_REAL)
print(f"Done in {time.time() - t0:.0f}s")'''

checks = '''# 5) CHECKS
for t in ["PRODUCTS", "PARTNERS", "TRULINE_PAMS", "PARTNER_REPS", "ACCOUNTS", "SUBSCRIPTIONS",
          "SUBSCRIPTION_MONTHLY", "ACCOUNT_MONTHLY", "CONSUMPTION_MONTHLY"]:
    print(f"{t:22s}", f"{session.table(t).count():,}")
# MONTH should be DATE. If it shows NUMBER/VARCHAR, tell Claude - one-line fix.
session.sql(f"""SELECT column_name, data_type FROM {DB}.information_schema.columns
               WHERE table_schema = '{SCHEMA}' AND table_name = 'ACCOUNT_MONTHLY' ORDER BY ordinal_position""").show(30)
session.sql("""SELECT MAX(ABS(START_ARR + NEW_ARR + EXPANSION_ARR - CONTRACTION_ARR - CHURN_ARR
                              - MIGRATED_OUT_ARR + MIGRATED_IN_ARR - END_ARR)) AS BRIDGE_MAX_ERROR
               FROM ACCOUNT_MONTHLY""").show()
session.sql("""SELECT BILLING_MODEL, COUNT(*) AS ACCOUNTS, ROUND(SUM(END_ARR) / 1e6, 1) AS ARR_M,
                      ROUND(SUM(CONSUMPTION_ARR) / 1e6, 1) AS CONSUMPTION_ARR_M
               FROM ACCOUNT_MONTHLY WHERE MONTH = (SELECT MAX(MONTH) FROM ACCOUNT_MONTHLY)
               GROUP BY 1 ORDER BY 2 DESC""").show()
session.sql("""SELECT COVERAGE_MODEL, COUNT(*) AS PARTNERS, COUNT(DISTINCT PAM_ID) AS PAMS,
                      ROUND(SUM(CURRENT_MANAGED_ARR) / 1e6, 1) AS ARR_M
               FROM PARTNERS GROUP BY 1 ORDER BY 4 DESC""").show()
session.sql("""SELECT TITLE, COUNT(*) AS REPS, ROUND(AVG(BOOK_ACTIVE_ACCOUNTS)) AS AVG_ACCOUNTS,
                      ROUND(AVG(BOOK_ARR)) AS AVG_BOOK_ARR
               FROM PARTNER_REPS GROUP BY 1 ORDER BY 2 DESC""").show()
session.sql("""SELECT BURN_STATUS, COUNT(*) AS ACCOUNTS, ROUND(SUM(COMMIT_ARR) / 1e6, 1) AS COMMIT_ARR_M
               FROM CONSUMPTION_MONTHLY WHERE MONTH = (SELECT MAX(MONTH) FROM CONSUMPTION_MONTHLY)
               GROUP BY 1 ORDER BY 2 DESC""").show()
session.sql("""
WITH lm AS (SELECT MAX(MONTH) AS m FROM ACCOUNT_MONTHLY),
b AS (SELECT ACCOUNT_ID, END_ARR AS arr0 FROM ACCOUNT_MONTHLY, lm WHERE MONTH = DATEADD(month, -12, lm.m) AND END_ARR > 0),
c AS (SELECT ACCOUNT_ID, END_ARR AS arr1 FROM ACCOUNT_MONTHLY, lm WHERE MONTH = lm.m)
SELECT a.SEGMENT, COUNT(*) AS BASE_ACCOUNTS,
       ROUND(SUM(COALESCE(c.arr1, 0)) / SUM(b.arr0), 3) AS NRR,
       ROUND(SUM(LEAST(COALESCE(c.arr1, 0), b.arr0)) / SUM(b.arr0), 3) AS GRR
FROM b JOIN ACCOUNTS a USING (ACCOUNT_ID) LEFT JOIN c USING (ACCOUNT_ID)
GROUP BY ROLLUP (a.SEGMENT) ORDER BY 1""").show()
session.sql("""SELECT RISK_BAND, COUNT(*) AS ACCOUNTS, ROUND(AVG(CHURN_PROB_90D), 3) AS AVG_CHURN_PROB_90D
               FROM ACCOUNT_MONTHLY WHERE MONTH = (SELECT MAX(MONTH) FROM ACCOUNT_MONTHLY)
               GROUP BY 1 ORDER BY 2 DESC""").show()'''

views = '''# 6) APP VIEWS
session.sql("""
CREATE OR REPLACE VIEW V_ACCOUNT_LATEST AS
SELECT a.*, p.PARTNER_NAME, p.TIER AS PARTNER_TIER, p.COVERAGE_MODEL AS PARTNER_COVERAGE,
       r.REP_NAME AS PARTNER_REP_NAME, r.TITLE AS PARTNER_REP_TITLE, r.EMAIL AS PARTNER_REP_EMAIL,
       k.PAM_ID, k.PAM_NAME, k.EMAIL AS PAM_EMAIL, m.MONTH AS AS_OF_MONTH, m.END_ARR, m.SEAT_ARR,
       m.CONSUMPTION_ARR, m.OVERAGE_REVENUE, m.CREDITS_CONSUMED, m.SEATS, m.ACTIVE_USERS,
       m.SEAT_UTILIZATION, m.HEALTH_SCORE, m.HEALTH_SCORE_CHANGE_3M, m.RISK_BAND, m.CHURN_PROB_90D,
       m.DRIVER_1, m.DRIVER_2, m.MONTHS_TO_RENEWAL
FROM ACCOUNTS a
JOIN PARTNERS p ON p.PARTNER_ID = a.PARTNER_ID
LEFT JOIN PARTNER_REPS r ON r.REP_ID = a.PARTNER_REP_ID
LEFT JOIN TRULINE_PAMS k ON k.PAM_ID = p.PAM_ID
JOIN ACCOUNT_MONTHLY m ON m.ACCOUNT_ID = a.ACCOUNT_ID
QUALIFY ROW_NUMBER() OVER (PARTITION BY a.ACCOUNT_ID ORDER BY m.MONTH DESC) = 1""").collect()

session.sql("""
CREATE OR REPLACE VIEW V_OUTREACH_QUEUE AS
SELECT ACCOUNT_ID, ACCOUNT_NAME, DOMAIN, IS_REAL_COMPANY, SEGMENT, INDUSTRY, COUNTRY, PARTNER_ID, PARTNER_NAME,
       PARTNER_COVERAGE, PARTNER_REP_ID, PARTNER_REP_NAME, PARTNER_REP_EMAIL, PAM_NAME, PAM_EMAIL, BILLING_MODEL, END_ARR, SEAT_ARR, CONSUMPTION_ARR, SEAT_UTILIZATION, HEALTH_SCORE, HEALTH_SCORE_CHANGE_3M, RISK_BAND, CHURN_PROB_90D,
       DRIVER_1, DRIVER_2, MONTHS_TO_RENEWAL, ROUND(END_ARR * CHURN_PROB_90D, 0) AS ARR_AT_RISK
FROM V_ACCOUNT_LATEST
WHERE STATUS = 'Active' AND (RISK_BAND IN ('At Risk', 'Critical') OR HEALTH_SCORE_CHANGE_3M <= -15)""").collect()

session.sql("""
CREATE OR REPLACE VIEW V_CONSUMPTION_WATCH AS
SELECT c.MONTH AS AS_OF_MONTH, c.ACCOUNT_ID, a.ACCOUNT_NAME, a.DOMAIN, a.IS_REAL_COMPANY, a.SEGMENT,
       c.PARTNER_ID, p.PARTNER_NAME, r.REP_NAME AS PARTNER_REP_NAME, k.PAM_NAME, c.CONTRACT_MONTH, 12 - c.CONTRACT_MONTH AS MONTHS_LEFT_IN_CONTRACT,
       c.ANNUAL_COMMIT_CREDITS, c.CREDITS_USED_CONTRACT_YTD, c.CREDITS_REMAINING, c.BURN_PACE, c.BURN_STATUS,
       c.COMMIT_ARR, c.OVERAGE_REVENUE,
       CASE WHEN c.BURN_STATUS = 'Ahead of pace' THEN 'Top-up / expansion opportunity'
            WHEN c.BURN_STATUS = 'Below pace' AND c.CONTRACT_MONTH >= 8 THEN 'Commitment at risk at renewal'
            WHEN c.BURN_STATUS = 'Below pace' THEN 'Drive adoption'
            ELSE 'On track' END AS RECOMMENDED_ACTION,
       ROUND(c.COMMIT_ARR * GREATEST(0, 1 - c.BURN_PACE), 0) AS COMMIT_ARR_AT_RISK
FROM CONSUMPTION_MONTHLY c
JOIN ACCOUNTS a ON a.ACCOUNT_ID = c.ACCOUNT_ID
JOIN PARTNERS p ON p.PARTNER_ID = c.PARTNER_ID
LEFT JOIN PARTNER_REPS r ON r.REP_ID = a.PARTNER_REP_ID
LEFT JOIN TRULINE_PAMS k ON k.PAM_ID = p.PAM_ID
WHERE c.MONTH = (SELECT MAX(MONTH) FROM CONSUMPTION_MONTHLY)""").collect()

session.sql("""
CREATE OR REPLACE VIEW V_PARTNER_SCORECARD AS
WITH lm AS (SELECT MAX(MONTH) AS m FROM ACCOUNT_MONTHLY),
b AS (SELECT am.PARTNER_ID, am.ACCOUNT_ID, am.END_ARR AS arr0 FROM ACCOUNT_MONTHLY am, lm
      WHERE am.MONTH = DATEADD(month, -12, lm.m) AND am.END_ARR > 0),
c AS (SELECT am.ACCOUNT_ID, am.END_ARR AS arr1, am.CONSUMPTION_ARR AS cons1, am.RISK_BAND
      FROM ACCOUNT_MONTHLY am, lm WHERE am.MONTH = lm.m),
mg AS (SELECT am.PARTNER_ID, SUM(am.MIGRATED_OUT_ARR) AS mig_out, SUM(am.MIGRATED_IN_ARR) AS mig_in
       FROM ACCOUNT_MONTHLY am, lm WHERE am.MONTH > DATEADD(month, -12, lm.m) GROUP BY 1)
SELECT p.PARTNER_ID, p.PARTNER_NAME, p.TIER, p.REGION, p.SPECIALIZATION, p.COVERAGE_MODEL, k.PAM_NAME,
       COUNT(*) AS BASE_ACCOUNTS, SUM(b.arr0) AS ARR_12M_AGO, SUM(COALESCE(c.arr1, 0)) AS ARR_NOW,
       ROUND(SUM(COALESCE(c.arr1, 0)) / NULLIF(SUM(b.arr0), 0), 3) AS NRR,
       ROUND(SUM(LEAST(COALESCE(c.arr1, 0), b.arr0)) / NULLIF(SUM(b.arr0), 0), 3) AS GRR,
       SUM(IFF(c.RISK_BAND IN ('At Risk', 'Critical'), c.arr1, 0)) AS ARR_IN_AT_RISK_ACCOUNTS,
       ROUND(SUM(COALESCE(c.cons1, 0)) / NULLIF(SUM(COALESCE(c.arr1, 0)), 0), 3) AS CONSUMPTION_SHARE_OF_ARR,
       ANY_VALUE(COALESCE(mg.mig_out, 0)) AS SEAT_ARR_MIGRATED_12M,
       ROUND(ANY_VALUE(mg.mig_in) / NULLIF(ANY_VALUE(mg.mig_out), 0), 3) AS MIGRATION_UPLIFT
FROM b JOIN PARTNERS p ON p.PARTNER_ID = b.PARTNER_ID LEFT JOIN c ON c.ACCOUNT_ID = b.ACCOUNT_ID
LEFT JOIN mg ON mg.PARTNER_ID = b.PARTNER_ID
LEFT JOIN TRULINE_PAMS k ON k.PAM_ID = p.PAM_ID
GROUP BY 1, 2, 3, 4, 5, 6, 7""").collect()

session.sql("""
CREATE OR REPLACE VIEW V_REP_BOOK AS
SELECT r.REP_ID, r.REP_NAME, r.TITLE, r.SEGMENT_FOCUS, r.EMAIL, r.PARTNER_ID, p.PARTNER_NAME, p.COVERAGE_MODEL,
       COUNT(l.ACCOUNT_ID) AS ACTIVE_ACCOUNTS, SUM(l.END_ARR) AS BOOK_ARR, SUM(l.CONSUMPTION_ARR) AS CONSUMPTION_ARR,
       SUM(IFF(l.RISK_BAND IN ('At Risk', 'Critical'), l.END_ARR, 0)) AS AT_RISK_ARR,
       ROUND(AVG(l.HEALTH_SCORE), 1) AS AVG_HEALTH_SCORE,
       SUM(IFF(l.HEALTH_SCORE_CHANGE_3M <= -15, 1, 0)) AS ACCOUNTS_DETERIORATING
FROM PARTNER_REPS r
JOIN PARTNERS p ON p.PARTNER_ID = r.PARTNER_ID
LEFT JOIN V_ACCOUNT_LATEST l ON l.PARTNER_REP_ID = r.REP_ID AND l.STATUS = 'Active'
GROUP BY 1, 2, 3, 4, 5, 6, 7, 8""").collect()

session.sql("""
CREATE OR REPLACE VIEW V_PAM_PORTFOLIO AS
SELECT k.PAM_ID, k.PAM_NAME, k.EMAIL, k.COVERAGE_MODEL, k.REGION, COUNT(DISTINCT p.PARTNER_ID) AS PARTNERS,
       COUNT(l.ACCOUNT_ID) AS ACTIVE_ACCOUNTS, SUM(l.END_ARR) AS PORTFOLIO_ARR,
       SUM(l.CONSUMPTION_ARR) AS CONSUMPTION_ARR,
       SUM(IFF(l.RISK_BAND IN ('At Risk', 'Critical'), l.END_ARR, 0)) AS AT_RISK_ARR
FROM TRULINE_PAMS k
JOIN PARTNERS p ON p.PAM_ID = k.PAM_ID
LEFT JOIN V_ACCOUNT_LATEST l ON l.PARTNER_ID = p.PARTNER_ID AND l.STATUS = 'Active'
GROUP BY 1, 2, 3, 4, 5""").collect()

session.sql("SELECT * FROM V_OUTREACH_QUEUE ORDER BY ARR_AT_RISK DESC LIMIT 10").show()
session.sql("SELECT RECOMMENDED_ACTION, COUNT(*) AS ACCOUNTS, SUM(COMMIT_ARR) AS COMMIT_ARR FROM V_CONSUMPTION_WATCH GROUP BY 1").show()
session.sql("SELECT * FROM V_PAM_PORTFOLIO ORDER BY AT_RISK_ARR DESC LIMIT 10").show()'''


def code(src):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
            "source": src.splitlines(keepends=True)}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
                   "language_info": {"name": "python"}},
      "cells": [md(md_intro), code(setup), md(real_md), code(real_a), code(real_b),
                md("## 3) Generator code\nRun this cell once; it only defines functions."),
                code("# 3) GENERATOR CODE\n" + gen_src),
                code(run), code(checks), code(views)]}
for i, cell in enumerate(nb["cells"]):
    cell["id"] = f"cell-{i}"
json.dump(nb, open(os.path.join(HERE, "truline_snowflake_notebook.ipynb"), "w"), indent=1)
print("cells:", len(nb["cells"]))
