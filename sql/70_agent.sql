-- Truline Coverage Agent (Cortex Agent, Claude orchestration) + Snowflake Intelligence. Run after 10-60.
-- Tools: governed metrics (semantic view), web search (company name/domain only), cited document generator,
-- approve plays, log actions. Everything runs as the asking user, so row access + masking policies apply.
USE ROLE ATTENDEE_ROLE;
USE SCHEMA TRULINE.APP;

-- Text-only wrappers: agent custom tools cannot take OBJECT parameters.
CREATE OR REPLACE PROCEDURE AGENT_APPROVE_PLAYS(CANDIDATE_IDS VARCHAR, NOTE VARCHAR)
RETURNS VARIANT LANGUAGE SQL
COMMENT = 'Agent tool: approve comma-separated play candidate IDs (C-...) the caller can see'
EXECUTE AS CALLER
AS
$$
DECLARE
  res VARIANT;
BEGIN
  CALL TRULINE.APP.APPROVE_PLAYS(SPLIT(REGEXP_REPLACE(:CANDIDATE_IDS, '\\s', ''), ','), :NOTE) INTO :res;
  RETURN res;
END;
$$;

CREATE OR REPLACE PROCEDURE AGENT_LOG_ACTION(ACTION VARCHAR, OBJECT_TYPE VARCHAR, OBJECT_ID VARCHAR, NOTE VARCHAR)
RETURNS VARCHAR LANGUAGE SQL
COMMENT = 'Agent tool: record a follow-up or decision in the audit log'
EXECUTE AS CALLER
AS
$$
BEGIN
  INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS)
  SELECT :ACTION, :OBJECT_TYPE, :OBJECT_ID, OBJECT_CONSTRUCT('note', :NOTE, 'source', 'agent');
  RETURN 'logged';
END;
$$;

CREATE OR REPLACE AGENT TRULINE_COVERAGE_AGENT
  COMMENT = 'Truline partner coverage agent: triage, plays, cited briefs, approvals'
  PROFILE = '{"display_name": "Truline Coverage Agent", "color": "blue"}'
FROM SPECIFICATION
$$
models:
  orchestration: claude-sonnet-4-5
orchestration:
  budget:
    seconds: 120
    tokens: 40000
instructions:
  response: >
    You work for Truline partner account managers (PAMs) and partner users. Be concise and action-oriented:
    lead with the decision or number, then the why. Always say which partner, account and owner rep a play
    belongs to. Data is synthetic. Some fields (churn probability, risk drivers, escalation reasons) are masked
    for partner users; never try to unmask or infer them. When you quote a generated document, keep its
    [F#] citations.
  orchestration: >
    Use CoverageMetrics for any number: ARR, NRR, GRR, at-risk ARR, credits, burn pace, plays, products,
    partners, reps. Rows are already limited to what the user may see; never claim data exists outside it.
    Use WebSearch only for "why now" context on a REAL company (IS_REAL_COMPANY = TRUE): search with the
    company name and domain only. Never put Truline metrics, ARR, health, plays or partner names in a web query.
    A why-now check looks at the last 6 months, favoring the last 90 days, for (a) expansion signals: new
    investment, growth, new projects or products, new markets or regions, acquisitions, hiring; and (b) headwinds:
    falling revenue or profit warnings, regulatory problems, market exits, layoffs or restructuring, paused or
    cancelled investments. Per account give: Signal (Expansion / Headwind / Mixed / No recent signal), 1-3 dated
    findings with sources, then Play alignment (Aligned / Misaligned / Unclear) against the account's current plays
    from CoverageMetrics, or the play the signals suggest if it has none, and a one-sentence recommendation
    (push now, deprioritize, switch to proactive right-size, watch). If nothing recent is found say "No recent
    signal"; discard findings older than 6 months even if relevant, give every finding a date and a source,
    and never invent dates or sources.
    Use CitedDocument when the user wants a brief, business review, monthly report or weekly plan summary;
    doc_type PARTNER (subject = partner ID like P0001, audience internal or partner), PARTNER_MONTHLY
    (partner ID, audience partner) or PAM_PORTFOLIO (subject = PAM ID like TP054, or ME). Present its
    rendered text and claim-check status.
    Use ApprovePlays only after the user explicitly says to approve; pass CANDIDATE_ID values (C-...).
    Use LogAction to record a decision or follow-up the user asks you to note.
  sample_questions:
    - question: "Which of my partners need me this week, and why?"
    - question: "What are the top 5 plays by expected ARR and who owns them?"
    - question: "Why now for Michelin? Check the news and our numbers."
    - question: "Write a partner-shareable business review for P0001."
    - question: "Approve the top rescue play for Granite BIM Labs."
tools:
  - tool_spec:
      type: cortex_analyst_text_to_sql
      name: CoverageMetrics
      description: >
        Governed Truline coverage data (semantic view TRULINE_COVERAGE): accounts, partners, partner reps,
        PAMs, credit contracts, product subscriptions and this week's scored plays (with CANDIDATE_ID,
        owner rep, value, routing and escalation). Metrics: total ARR, NRR, GRR, at-risk ARR, expected ARR at
        risk, consumption ARR and share, burn pace, commit at risk, projected shortfall, play count and value.
  - tool_spec:
      type: web_search
      name: WebSearch
  - tool_spec:
      type: generic
      name: CitedDocument
      description: >
        Generates a document with Claude where every number is a cited fact from the semantic view and a claim
        checker rejects uncited numbers. Returns doc_id, status (PASS, PASS_WITH_WARNINGS, FAIL), rendered text.
      input_schema:
        type: object
        properties:
          doc_type:
            type: string
            description: "PARTNER, PARTNER_MONTHLY or PAM_PORTFOLIO"
          subject_id:
            type: string
            description: "Partner ID (P0001) for PARTNER/PARTNER_MONTHLY, PAM ID (TP054) or ME for PAM_PORTFOLIO"
          audience:
            type: string
            description: "internal or partner"
          model:
            type: string
            description: "Always claude-sonnet-4-5"
        required: [doc_type, subject_id, audience, model]
  - tool_spec:
      type: generic
      name: ApprovePlays
      description: Approve play candidates (writes PLAYS and AUDIT_LOG). Only when the user explicitly approves.
      input_schema:
        type: object
        properties:
          candidate_ids:
            type: string
            description: "Comma-separated CANDIDATE_ID values, e.g. C-cb4e4357c928,C-0388d15027b9"
          note:
            type: string
            description: "Short reason, e.g. 'approved via agent'"
        required: [candidate_ids, note]
  - tool_spec:
      type: generic
      name: LogAction
      description: Record a decision or follow-up in the audit log.
      input_schema:
        type: object
        properties:
          action:
            type: string
            description: "Short verb, e.g. FOLLOW_UP or DECISION"
          object_type:
            type: string
            description: "PARTNER, ACCOUNT or PLAY"
          object_id:
            type: string
            description: "Partner ID, account ID or candidate ID"
          note:
            type: string
            description: "What was decided or needs to happen"
        required: [action, object_type, object_id, note]
  - tool_spec:
      type: data_to_chart
      name: data_to_chart
      description: Generates visualizations from data
tool_resources:
  CoverageMetrics:
    semantic_view: TRULINE.APP.TRULINE_COVERAGE
    execution_environment:
      type: warehouse
      warehouse: DEFAULT_WH
  WebSearch:
    max_results: 5
  CitedDocument:
    type: procedure
    identifier: TRULINE.APP.GENERATE_DOC
    execution_environment:
      type: warehouse
      warehouse: DEFAULT_WH
  ApprovePlays:
    type: procedure
    identifier: TRULINE.APP.AGENT_APPROVE_PLAYS
    execution_environment:
      type: warehouse
      warehouse: DEFAULT_WH
  LogAction:
    type: procedure
    identifier: TRULINE.APP.AGENT_LOG_ACTION
    execution_environment:
      type: warehouse
      warehouse: DEFAULT_WH
$$;

GRANT USAGE ON AGENT TRULINE_COVERAGE_AGENT TO ROLE TRULINE_PAM;
GRANT USAGE ON AGENT TRULINE_COVERAGE_AGENT TO ROLE TRULINE_PARTNER;
GRANT USAGE ON AGENT TRULINE_COVERAGE_AGENT TO ROLE TRULINE_OPS;

-- Snowflake Intelligence: account-level object listing the agents users see.
USE ROLE ACCOUNTADMIN;
CREATE SNOWFLAKE INTELLIGENCE IF NOT EXISTS SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT;
EXECUTE IMMEDIATE $$
BEGIN
  ALTER SNOWFLAKE INTELLIGENCE SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT ADD AGENT TRULINE.APP.TRULINE_COVERAGE_AGENT;
  RETURN 'added';
EXCEPTION
  WHEN OTHER THEN RETURN 'already listed';
END;
$$;
GRANT USAGE ON SNOWFLAKE INTELLIGENCE SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT TO ROLE TRULINE_PAM;
GRANT USAGE ON SNOWFLAKE INTELLIGENCE SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT TO ROLE TRULINE_PARTNER;
GRANT USAGE ON SNOWFLAKE INTELLIGENCE SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT TO ROLE TRULINE_OPS;
GRANT USAGE ON SNOWFLAKE INTELLIGENCE SNOWFLAKE_INTELLIGENCE_OBJECT_DEFAULT TO ROLE ATTENDEE_ROLE;

-- Let the Streamlit app (restricted caller's rights) call the agent as the viewer.
GRANT CALLER USAGE ON AGENT TRULINE.APP.TRULINE_COVERAGE_AGENT TO ROLE ATTENDEE_ROLE;
