-- Governed metric definitions. Cortex Analyst, the agent and the fact builder all read metrics from here,
-- so every cited number traces back to one definition. Built on the policy-protected APP views.
CREATE OR REPLACE SEMANTIC VIEW TRULINE.APP.TRULINE_COVERAGE
  TABLES (
    accounts AS TRULINE.APP.ACCOUNTS PRIMARY KEY (ACCOUNT_ID)
      WITH SYNONYMS = ('customers', 'end customers') COMMENT = 'Customer accounts at the latest month (Sep 2026)',
    partners AS TRULINE.APP.PARTNERS PRIMARY KEY (PARTNER_ID)
      WITH SYNONYMS = ('resellers', 'channel partners') COMMENT = 'Reseller partners and their coverage model',
    reps AS TRULINE.APP.PARTNER_REPS PRIMARY KEY (REP_ID)
      WITH SYNONYMS = ('partner reps', 'account owners') COMMENT = 'Partner sales reps',
    consumption AS TRULINE.APP.CONSUMPTION PRIMARY KEY (ACCOUNT_ID)
      WITH SYNONYMS = ('credits', 'credit contracts') COMMENT = 'Prepaid credit contracts at the latest month',
    plays AS TRULINE.APP.PLAY_CANDIDATES PRIMARY KEY (CANDIDATE_ID)
      WITH SYNONYMS = ('play candidates', 'recommendations') COMMENT = 'This week''s scored plays',
    subscriptions AS TRULINE.APP.SUBSCRIPTIONS PRIMARY KEY (SUBSCRIPTION_ID)
      COMMENT = 'Current product subscriptions',
    products AS TRULINE.APP.PRODUCTS PRIMARY KEY (PRODUCT_CODE) COMMENT = 'Truline product catalog'
  )
  RELATIONSHIPS (
    accounts_to_partners AS accounts (PARTNER_ID) REFERENCES partners,
    accounts_to_reps AS accounts (PARTNER_REP_ID) REFERENCES reps,
    consumption_to_accounts AS consumption (ACCOUNT_ID) REFERENCES accounts,
    plays_to_accounts AS plays (ACCOUNT_ID) REFERENCES accounts,
    subscriptions_to_accounts AS subscriptions (ACCOUNT_ID) REFERENCES accounts,
    subscriptions_to_products AS subscriptions (PRODUCT_CODE) REFERENCES products
  )
  FACTS (
    accounts.arr_now AS ARR_NOW COMMENT = 'Account ARR at the latest month (seat ARR + credit commit ARR); 0 if churned',
    accounts.arr_12m_ago AS ARR_12M_AGO COMMENT = 'Account ARR 12 months before the latest month',
    accounts.seat_arr_value AS SEAT_ARR COMMENT = 'Seat subscription ARR',
    accounts.consumption_arr_value AS CONSUMPTION_ARR COMMENT = 'Prepaid credit commitment ARR',
    accounts.churn_prob AS CHURN_PROB_90D COMMENT = 'Modelled probability of churn in the next 90 days (internal)',
    accounts.health AS HEALTH_SCORE COMMENT = 'Health score 0-100',
    consumption.credits_used_ytd AS CREDITS_USED_CONTRACT_YTD,
    consumption.credits_expected_to_date AS EXPECTED_CREDITS_TO_DATE COMMENT = 'Commit x contract month / 12',
    consumption.commit_arr_value AS COMMIT_ARR,
    consumption.commit_at_risk_value AS COMMIT_ARR_AT_RISK COMMENT = 'Commit ARR x (1 - burn pace)',
    consumption.shortfall_value AS PROJECTED_SHORTFALL_USD COMMENT = 'Projected credits beyond commit x price per credit',
    plays.play_value_usd AS VALUE_USD COMMENT = 'Expected ARR impact of the play (see VALUE_BASIS)',
    subscriptions.product_arr_value AS CURRENT_ARR,
    subscriptions.product_seats AS CURRENT_SEATS
  )
  DIMENSIONS (
    accounts.account_id AS ACCOUNT_ID,
    accounts.account_name AS ACCOUNT_NAME WITH SYNONYMS = ('customer name', 'company'),
    accounts.domain AS DOMAIN,
    accounts.is_real_company AS IS_REAL_COMPANY COMMENT = 'TRUE when the name and domain are a real company (metrics are synthetic)',
    accounts.segment AS SEGMENT,
    accounts.industry AS INDUSTRY,
    accounts.industry_group AS INDUSTRY_GROUP,
    accounts.account_country AS COUNTRY,
    accounts.account_region AS REGION,
    accounts.account_status AS STATUS,
    accounts.billing_model AS BILLING_MODEL,
    accounts.risk_band AS RISK_BAND,
    accounts.as_of_month AS AS_OF_MONTH,
    accounts.months_to_renewal AS MONTHS_TO_RENEWAL,
    partners.partner_id AS PARTNER_ID,
    partners.partner_name AS PARTNER_NAME WITH SYNONYMS = ('reseller'),
    partners.partner_tier AS TIER,
    partners.partner_region AS REGION,
    partners.coverage_model AS COVERAGE_MODEL,
    partners.pam_id AS PAM_ID,
    partners.pam_name AS PAM_NAME WITH SYNONYMS = ('partner account manager'),
    partners.specialization AS SPECIALIZATION,
    reps.rep_id AS REP_ID,
    reps.rep_name AS REP_NAME,
    reps.rep_title AS TITLE,
    consumption.burn_status AS BURN_STATUS,
    consumption.contract_month AS CONTRACT_MONTH,
    plays.candidate_id AS CANDIDATE_ID,
    plays.play_partner_id AS PARTNER_ID,
    plays.play_family AS PLAY_FAMILY,
    plays.play_type AS PLAY_TYPE,
    plays.routed_to AS ROUTED_TO,
    plays.escalation_reason AS ESCALATION_REASON,
    plays.partner_needs_intervention AS PARTNER_NEEDS_INTERVENTION
      WITH SYNONYMS = ('needs intervention', 'needs the PAM', 'partners that need me')
      COMMENT = 'TRUE when the partner''s NRR is below 95% or more than 20% of its ARR is At Risk/Critical. This is THE definition of a partner needing PAM intervention.',
    plays.rep_over_cap AS REP_OVER_CAP COMMENT = 'TRUE when the owner rep has more than 5 plays this week',
    plays.owner_rep_name AS OWNER_REP_NAME,
    subscriptions.product_code AS PRODUCT_CODE,
    subscriptions.subscription_status AS STATUS,
    products.product_name AS PRODUCT_NAME,
    products.product_family AS PRODUCT_FAMILY
  )
  METRICS (
    accounts.total_arr AS SUM(accounts.arr_now) COMMENT = 'ARR at the latest month',
    accounts.total_seat_arr AS SUM(accounts.seat_arr_value) COMMENT = 'Seat ARR',
    accounts.total_consumption_arr AS SUM(accounts.consumption_arr_value) COMMENT = 'Consumption (credit commit) ARR',
    accounts.active_accounts AS SUM(IFF(accounts.account_status = 'Active', 1, 0)) COMMENT = 'Active customer accounts',
    accounts.at_risk_arr AS SUM(IFF(accounts.risk_band IN ('At Risk', 'Critical'), accounts.arr_now, 0))
      COMMENT = 'ARR in accounts whose risk band is At Risk or Critical',
    accounts.expected_arr_at_risk AS SUM(accounts.arr_now * COALESCE(accounts.churn_prob, 0))
      COMMENT = 'ARR x 90-day churn probability (internal)',
    accounts.nrr AS SUM(IFF(accounts.arr_12m_ago > 0, accounts.arr_now, 0)) / NULLIF(SUM(accounts.arr_12m_ago), 0)
      COMMENT = 'Net revenue retention: current ARR of accounts that had ARR 12 months ago / their ARR then',
    accounts.grr AS SUM(LEAST(accounts.arr_now, accounts.arr_12m_ago)) / NULLIF(SUM(accounts.arr_12m_ago), 0)
      COMMENT = 'Gross revenue retention: like NRR but expansion capped at the starting ARR',
    accounts.consumption_share AS SUM(accounts.consumption_arr_value) / NULLIF(SUM(accounts.arr_now), 0)
      COMMENT = 'Share of ARR on prepaid credits',
    accounts.avg_health_score AS AVG(accounts.health) COMMENT = 'Average health score of active accounts',
    consumption.portfolio_burn_pace AS SUM(consumption.credits_used_ytd) / NULLIF(SUM(consumption.credits_expected_to_date), 0)
      COMMENT = 'Credits used / credits expected to date (1.0 = on pace)',
    consumption.total_commit_arr AS SUM(consumption.commit_arr_value) COMMENT = 'Credit commitment ARR',
    consumption.total_commit_arr_at_risk AS SUM(consumption.commit_at_risk_value) COMMENT = 'Commit ARR at risk from under-burn',
    consumption.projected_shortfall AS SUM(consumption.shortfall_value) COMMENT = 'Projected top-up need in USD',
    plays.play_count AS COUNT(plays.candidate_id) COMMENT = 'Number of plays',
    plays.play_value AS SUM(plays.play_value_usd) COMMENT = 'Total expected ARR impact of plays',
    subscriptions.product_arr AS SUM(subscriptions.product_arr_value) COMMENT = 'ARR by product',
    subscriptions.product_seat_count AS SUM(subscriptions.product_seats) COMMENT = 'Seats by product'
  )
  COMMENT = 'Truline partner coverage: ARR, retention, risk, credits and plays (synthetic data)';

-- Re-apply grants dropped by CREATE OR REPLACE.
GRANT SELECT ON SEMANTIC VIEW TRULINE.APP.TRULINE_COVERAGE TO ROLE TRULINE_PAM;
GRANT SELECT ON SEMANTIC VIEW TRULINE.APP.TRULINE_COVERAGE TO ROLE TRULINE_PARTNER;
GRANT SELECT ON SEMANTIC VIEW TRULINE.APP.TRULINE_COVERAGE TO ROLE TRULINE_OPS;
