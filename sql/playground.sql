-- Playground: paste into a Snowsight SQL worksheet (role ATTENDEE_ROLE, warehouse DEFAULT_WH) and run one statement at a time.
USE ROLE ATTENDEE_ROLE;
USE WAREHOUSE DEFAULT_WH;
USE SCHEMA TRULINE.APP;

-- 1) Who am I and what can I see (admin user sees all 500 partners)
SELECT * FROM MY_SCOPE;

-- 2) Governed metrics from the semantic view, by coverage tier
SELECT * FROM SEMANTIC_VIEW(TRULINE_COVERAGE
  METRICS accounts.total_arr, accounts.active_accounts, accounts.nrr, accounts.grr, accounts.at_risk_arr
  DIMENSIONS partners.coverage_model);

-- 3) Noah Shelby's (shared PAM TP054) weekly plan: top plays, owner rep, routing
SELECT PAM_RANK, PLAY_TYPE, ACCOUNT_NAME, IS_REAL_COMPANY, PARTNER_NAME, OWNER_REP_NAME, VALUE_USD, VALUE_BASIS,
       ROUTED_TO, ESCALATION_REASON, MONTHS_TO_RENEWAL
FROM PLAY_CANDIDATES WHERE PAM_ID = 'TP054' ORDER BY PAM_RANK LIMIT 25;

-- 4) Partners that need Noah (NRR below 95% or >20% of ARR at risk)
SELECT PARTNER_NAME, ANY_VALUE(PARTNER_NRR) AS NRR, ANY_VALUE(PARTNER_AT_RISK_SHARE) AS AT_RISK_SHARE, COUNT(*) AS PLAYS
FROM PLAY_CANDIDATES WHERE PAM_ID = 'TP054' AND PARTNER_NEEDS_INTERVENTION GROUP BY 1 ORDER BY 2;

-- 5) Rep load: plays per rep this week vs the cap of 5
SELECT OWNER_REP_NAME, PARTNER_NAME, COUNT(*) AS PLAYS, SUM(IFF(REP_OVER_CAP, 1, 0)) AS OVER_CAP, SUM(VALUE_USD) AS VALUE_USD
FROM PLAY_CANDIDATES WHERE PAM_ID = 'TP054' GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15;

-- 6) Same query, different Snowflake users: row access + masking in action (simulated, no login needed)
EXECUTE USING POLICY_CONTEXT(CURRENT_ROLE => 'TRULINE_PAM', CURRENT_USER => 'NOAH_SHELBY')
  AS SELECT COUNT(DISTINCT PARTNER_ID) AS PARTNERS, COUNT(*) AS ACCOUNTS, MAX(CHURN_PROB_90D) AS MAX_CHURN_PROB FROM ACCOUNTS;
EXECUTE USING POLICY_CONTEXT(CURRENT_ROLE => 'TRULINE_PAM', CURRENT_USER => 'FATIMA_HAYES')
  AS SELECT COUNT(DISTINCT PARTNER_ID) AS PARTNERS, COUNT(*) AS ACCOUNTS, MAX(CHURN_PROB_90D) AS MAX_CHURN_PROB FROM ACCOUNTS;
EXECUTE USING POLICY_CONTEXT(CURRENT_ROLE => 'TRULINE_PARTNER', CURRENT_USER => 'VERTEX_PARTNER')
  AS SELECT COUNT(DISTINCT PARTNER_ID) AS PARTNERS, COUNT(*) AS ACCOUNTS, MAX(CHURN_PROB_90D) AS MAX_CHURN_PROB FROM ACCOUNTS;

-- 7) Generate a cited document with Claude (20-60 s). Copy DOC_ID from the result for step 8.
--    Types: ('PARTNER', '<partner id>', 'internal'|'partner'), ('PARTNER_MONTHLY', '<partner id>', 'partner'),
--           ('PAM_PORTFOLIO', '<pam id>', 'internal'). Try P0001 (top partner), P0370 (long tail), TP054.
CALL GENERATE_DOC('PARTNER', 'P0001', 'partner', 'claude-sonnet-4-5');

-- 8) Catch a made-up number: replace <DOC_ID> and run; status = FAIL, logged in AUDIT_LOG
CALL CHECK_CLAIMS('<DOC_ID>', 'Total ARR is {{F3}} and will grow to $4.7M next quarter.');

-- 9) Every fact behind a document: label, value, governing metric, source query ID
SELECT FACT_ID, LABEL, DISPLAY, METRIC, SOURCE_OBJECT, QUERY_ID FROM DOC_FACTS WHERE DOC_ID = '<DOC_ID>' ORDER BY TO_NUMBER(SUBSTR(FACT_ID, 2));

-- 10) Approve plays (writes PLAYS + AUDIT_LOG), then look at the trail
CALL APPROVE_PLAYS((SELECT ARRAY_AGG(CANDIDATE_ID) FROM (SELECT CANDIDATE_ID FROM PLAY_CANDIDATES WHERE PAM_ID = 'TP054' ORDER BY PAM_RANK LIMIT 3)), 'playground');
SELECT * FROM PLAYS ORDER BY CREATED_AT DESC;
SELECT EVENT_TS, USER_NAME, ACTION, OBJECT_ID, DETAILS FROM AUDIT_LOG ORDER BY EVENT_TS DESC LIMIT 20;

-- 11) Tune a play rule and refresh (e.g. lower the escalation threshold to $100K)
-- UPDATE TRULINE.CORE.PLAY_PARAMS SET VALUE = 100000 WHERE PARAM = 'ESCALATE_VALUE_USD';
-- ALTER DYNAMIC TABLE TRULINE.CORE.PLAY_CANDIDATES REFRESH;
