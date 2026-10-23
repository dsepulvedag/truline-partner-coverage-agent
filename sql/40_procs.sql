-- Agent/app tools. All run with CALLER's rights, so row access and masking policies apply to whoever calls:
-- a user can only create plays, facts and documents from rows they are allowed to see.
USE SCHEMA TRULINE.APP;

CREATE OR REPLACE PROCEDURE LOG_ACTION(ACTION VARCHAR, OBJECT_TYPE VARCHAR, OBJECT_ID VARCHAR, DETAILS VARIANT)
RETURNS VARCHAR LANGUAGE SQL COMMENT = 'Agent tool: record an action in the audit log'
EXECUTE AS CALLER
AS
$$
BEGIN
  INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS) SELECT :ACTION, :OBJECT_TYPE, :OBJECT_ID, :DETAILS;
  RETURN 'logged';
END;
$$;

CREATE OR REPLACE PROCEDURE APPROVE_PLAYS(CANDIDATE_IDS ARRAY, NOTE VARCHAR)
RETURNS VARIANT LANGUAGE SQL COMMENT = 'Agent/app tool: approve play candidates the caller can see; writes PLAYS and AUDIT_LOG'
EXECUTE AS CALLER
AS
$$
DECLARE
  requested INTEGER DEFAULT ARRAY_SIZE(:CANDIDATE_IDS);
  created INTEGER;
BEGIN
  INSERT INTO TRULINE.CORE.PLAYS (CANDIDATE_ID, WEEK_OF, ACCOUNT_ID, PARTNER_ID, PLAY_TYPE, OWNER_REP_ID, ROUTED_TO, VALUE_USD, STATUS, NOTE)
  SELECT c.CANDIDATE_ID, DATE_TRUNC('week', CURRENT_DATE()), c.ACCOUNT_ID, c.PARTNER_ID, c.PLAY_TYPE, c.OWNER_REP_ID,
         c.ROUTED_TO, c.VALUE_USD, IFF(c.ROUTED_TO = 'Rep', 'Delegated to rep', 'Approved by PAM'), :NOTE
  FROM TRULINE.APP.PLAY_CANDIDATES c
  WHERE c.CANDIDATE_ID IN (SELECT VALUE::VARCHAR FROM TABLE(FLATTEN(INPUT => :CANDIDATE_IDS)))
    AND NOT EXISTS (SELECT 1 FROM TRULINE.APP.PLAYS p
                    WHERE p.CANDIDATE_ID = c.CANDIDATE_ID AND p.WEEK_OF = DATE_TRUNC('week', CURRENT_DATE()));
  created := SQLROWCOUNT;
  INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS)
  SELECT 'APPROVE_PLAYS', 'PLAYS', NULL,
         OBJECT_CONSTRUCT('requested', :requested, 'created', :created, 'candidate_ids', :CANDIDATE_IDS, 'note', :NOTE);
  RETURN OBJECT_CONSTRUCT('requested', requested, 'created', created,
                          'not_created', requested - created,
                          'reason_if_not_created', 'not visible to you under row access policy, or already approved this week');
END;
$$;

-- Owner's-rights LLM gateway. Restricted caller's-rights sessions (Streamlit) cannot use SNOWFLAKE.CORTEX directly
-- (no caller grants on shared objects). It only forwards a prompt; the facts in the prompt were built with the
-- caller's rights, so the model never sees rows the caller cannot see.
CREATE OR REPLACE PROCEDURE LLM_COMPLETE(MODEL VARCHAR, PROMPT VARCHAR)
RETURNS VARCHAR LANGUAGE SQL
COMMENT = 'Claude via AI_COMPLETE for caller-rights apps; approved Claude models only'
EXECUTE AS OWNER
AS
$$
BEGIN
  IF (MODEL NOT IN ('claude-sonnet-4-5', 'claude-sonnet-5-5', 'claude-opus-5-5', 'claude-haiku-4-5')) THEN
    RETURN 'ERROR: model not approved';
  END IF;
  LET out VARCHAR := (SELECT SNOWFLAKE.CORTEX.AI_COMPLETE(:MODEL, :PROMPT));
  RETURN out;
END;
$$;

-- Builds the citable fact set for one document from the semantic view (governed metrics) and the APP views.
CREATE OR REPLACE PROCEDURE BUILD_FACTS(DOC_TYPE VARCHAR, SUBJECT_ID VARCHAR, AUDIENCE VARCHAR)
RETURNS VARIANT LANGUAGE PYTHON RUNTIME_VERSION = '3.11' PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run' COMMENT = 'Claim checker step 1: compute numbered facts (F1..Fn) with metric definition and source query ID'
EXECUTE AS CALLER
AS
$$
import json, re, uuid

SV = "TRULINE.APP.TRULINE_COVERAGE"
ACCOUNT_METRICS = [("total_arr", "Total ARR", "usd", False), ("active_accounts", "Active accounts", "count", False),
                   ("nrr", "Net revenue retention (12 mo)", "pct", False), ("grr", "Gross revenue retention (12 mo)", "pct", False),
                   ("at_risk_arr", "ARR in At Risk or Critical accounts", "usd", False),
                   ("expected_arr_at_risk", "Expected ARR at risk (churn-probability weighted)", "usd", True),
                   ("total_consumption_arr", "Consumption (credit commit) ARR", "usd", False),
                   ("consumption_share", "Share of ARR on credits", "pct", False),
                   ("avg_health_score", "Average health score", "score", False)]
CREDIT_METRICS = [("portfolio_burn_pace", "Credit burn pace (1.00x = on pace)", "ratio", False),
                  ("total_commit_arr", "Credit commit ARR", "usd", False),
                  ("total_commit_arr_at_risk", "Commit ARR at risk from under-burn", "usd", False),
                  ("projected_shortfall", "Projected credit top-up need", "usd", False)]

def fmt(v, unit):
    if v is None:
        return None
    v = float(v)
    if unit == "usd":
        a = abs(v)
        return (f"${v/1e9:.2f}B" if a >= 1e9 else f"${v/1e6:.1f}M" if a >= 1e6 else f"${v/1e3:.0f}K" if a >= 1e3 else f"${v:,.0f}")
    if unit == "pct":
        return f"{v*100:.1f}%"
    if unit == "ratio":
        return f"{v:.2f}x"
    return f"{v:,.0f}"

def run(session, doc_type, subject_id, audience):
    doc_type, audience = doc_type.upper(), (audience or "internal").lower()
    scope = session.sql("SELECT USER_NAME, PAM_ID FROM TRULINE.APP.MY_SCOPE").collect()[0]
    if doc_type == "PAM_PORTFOLIO" and (subject_id or "ME").upper() == "ME":
        subject_id = scope["PAM_ID"]
    if not subject_id or not re.fullmatch(r"[A-Z0-9_]+", subject_id):
        return {"error": "subject_id must be a partner ID (P0123) or PAM ID (TP054)"}
    if doc_type in ("PARTNER", "PARTNER_MONTHLY"):
        where, label_sql = f"partners.partner_id = '{subject_id}'", f"SELECT PARTNER_NAME FROM TRULINE.APP.PARTNERS WHERE PARTNER_ID = '{subject_id}'"
        play_filter = f"PARTNER_ID = '{subject_id}'"
    elif doc_type == "PAM_PORTFOLIO":
        where, label_sql = f"partners.pam_id = '{subject_id}'", f"SELECT ANY_VALUE(PAM_NAME) FROM TRULINE.APP.PARTNERS WHERE PAM_ID = '{subject_id}'"
        play_filter = f"PAM_ID = '{subject_id}'"
    else:
        return {"error": "doc_type must be PARTNER, PARTNER_MONTHLY or PAM_PORTFOLIO"}

    name = session.sql(label_sql).collect()
    if not name or name[0][0] is None:
        session.sql("INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS) SELECT 'BUILD_FACTS_DENIED', ?, ?, NULL",
                    params=[doc_type, subject_id]).collect()
        return {"error": f"{subject_id} is not visible to {scope['USER_NAME']} (row access policy)"}

    doc_id = "D-" + uuid.uuid4().hex[:10]
    facts = []
    def add(label, value, unit, metric, source, filters, internal, qid, text=None):
        display = text if unit == "text" else fmt(value, unit)
        if display is None:
            return
        facts.append([doc_id, f"F{len(facts) + 1}", label, None if unit == "text" else float(value), text, display, unit,
                      metric, source, filters, internal, qid])
    def last_qid():
        return session.sql("SELECT LAST_QUERY_ID(-2)").collect()[0][0]

    as_of = session.sql("SELECT TO_CHAR(DATA_AS_OF, 'Mon YYYY') FROM TRULINE.APP.MY_SCOPE").collect()[0][0]
    add("Subject", None, "text", None, label_sql.split(" FROM ")[1].split(" ")[0], where, False, None, text=name[0][0])
    add("Data as of", None, "text", None, "TRULINE.APP.MY_SCOPE", None, False, None, text=as_of)

    for metrics, kind in ((ACCOUNT_METRICS, "accounts"), (CREDIT_METRICS, "consumption")):
        cols = ", ".join(f"{kind}.{m}" for m, _, _, _ in metrics)
        row = session.sql(f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS {cols} WHERE {where})").collect()
        qid = last_qid()
        for m, label, unit, internal in metrics:
            add(label, row[0][m.upper()] if row else None, unit, f"{kind}.{m}", SV, where, internal, qid)

    rows = session.sql(f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS plays.play_count, plays.play_value "
                       f"DIMENSIONS plays.play_family WHERE {where}) ORDER BY PLAY_VALUE DESC").collect()
    qid = last_qid()
    for r in rows:
        add(f"{r['PLAY_FAMILY']} plays this week", r["PLAY_COUNT"], "count", "plays.play_count", SV, where, False, qid)
        add(f"{r['PLAY_FAMILY']} plays expected ARR impact", r["PLAY_VALUE"], "usd", "plays.play_value", SV, where, False, qid)

    rows = session.sql(f"SELECT * FROM SEMANTIC_VIEW({SV} METRICS subscriptions.product_arr DIMENSIONS products.product_family "
                       f"WHERE {where}) WHERE PRODUCT_ARR > 0 ORDER BY PRODUCT_ARR DESC LIMIT 4").collect()
    qid = last_qid()
    for r in rows:
        add(f"{r['PRODUCT_FAMILY']} product ARR", r["PRODUCT_ARR"], "usd", "subscriptions.product_arr", SV, where, False, qid)

    rows = session.sql(f"""SELECT ACCOUNT_NAME, PARTNER_NAME, PLAY_TYPE, VALUE_USD, OWNER_REP_NAME, ROUTED_TO, ESCALATION_REASON,
                                  MONTHS_TO_RENEWAL FROM TRULINE.APP.PLAY_CANDIDATES WHERE {play_filter}
                           ORDER BY VALUE_USD DESC, MONTHS_TO_RENEWAL LIMIT 5""").collect()
    qid = last_qid()
    src = "TRULINE.APP.PLAY_CANDIDATES"
    for i, r in enumerate(rows, 1):
        add(f"Top play {i} account", None, "text", None, src, play_filter, False, qid, text=r["ACCOUNT_NAME"])
        if doc_type == "PAM_PORTFOLIO":
            add(f"Top play {i} partner", None, "text", None, src, play_filter, False, qid, text=r["PARTNER_NAME"])
        add(f"Top play {i} type", None, "text", None, src, play_filter, False, qid, text=r["PLAY_TYPE"])
        add(f"Top play {i} expected ARR impact", r["VALUE_USD"], "usd", "plays.play_value", src, play_filter, False, qid)
        add(f"Top play {i} owner rep", None, "text", None, src, play_filter, False, qid, text=r["OWNER_REP_NAME"])
        add(f"Top play {i} months to renewal", r["MONTHS_TO_RENEWAL"], "count", None, src, play_filter, False, qid)
        if r["ESCALATION_REASON"]:
            add(f"Top play {i} escalation reason", None, "text", None, src, play_filter, True, qid, text=r["ESCALATION_REASON"])

    if doc_type == "PAM_PORTFOLIO":
        rows = session.sql(f"""SELECT PARTNER_NAME, ANY_VALUE(PARTNER_NRR) AS NRR, ANY_VALUE(PARTNER_AT_RISK_SHARE) AS AT_RISK_SHARE
                               FROM TRULINE.APP.PLAY_CANDIDATES WHERE {play_filter} AND PARTNER_NEEDS_INTERVENTION
                               GROUP BY 1 ORDER BY 2 LIMIT 3""").collect()
        qid = last_qid()
        for i, r in enumerate(rows, 1):
            add(f"Partner needing you {i}", None, "text", None, src, play_filter, True, qid, text=r["PARTNER_NAME"])
            add(f"Partner needing you {i} NRR", r["NRR"], "pct", "accounts.nrr", src, play_filter, True, qid)
            add(f"Partner needing you {i} at-risk ARR share", r["AT_RISK_SHARE"], "pct", None, src, play_filter, True, qid)

    cols = ["DOC_ID", "FACT_ID", "LABEL", "VALUE", "TEXT_VALUE", "DISPLAY", "UNIT", "METRIC", "SOURCE_OBJECT", "FILTERS",
            "INTERNAL_ONLY", "QUERY_ID"]
    types = ["VARCHAR"] * 3 + ["FLOAT"] + ["VARCHAR"] * 6 + ["BOOLEAN", "VARCHAR"]
    select = ", ".join(f"f.value[{i}]::{t}" for i, t in enumerate(types))
    session.sql(f"INSERT INTO TRULINE.CORE.DOC_FACTS ({', '.join(cols)}) SELECT {select} FROM TABLE(FLATTEN(PARSE_JSON(?))) f",
                params=[json.dumps(facts)]).collect()
    session.sql("INSERT INTO TRULINE.CORE.DOCUMENTS (DOC_ID, DOC_TYPE, SUBJECT_ID, AUDIENCE, CHECK_STATUS) VALUES (?, ?, ?, ?, 'FACTS_READY')",
                params=[doc_id, doc_type, subject_id, audience]).collect()
    session.sql("INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS) "
                "SELECT 'BUILD_FACTS', 'DOCUMENT', ?, PARSE_JSON(?)",
                params=[doc_id, json.dumps({"doc_type": doc_type, "subject_id": subject_id, "audience": audience, "facts": len(facts)})]).collect()
    allowed = [f for f in facts if audience != "partner" or not f[10]]
    return {"doc_id": doc_id, "doc_type": doc_type, "subject_id": subject_id, "audience": audience,
            "facts": [{"id": f[1], "label": f[2], "display": f[5], "metric": f[7], "source": f[8], "internal_only": f[10]} for f in allowed]}
$$;

-- Validates a draft written with {{F#}} placeholders and renders it. Any number not coming from a fact fails the check.
CREATE OR REPLACE PROCEDURE CHECK_CLAIMS(DOC_ID VARCHAR, DRAFT VARCHAR)
RETURNS VARIANT LANGUAGE PYTHON RUNTIME_VERSION = '3.11' PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run' COMMENT = 'Claim checker step 2: reject any number in a draft that is not a cited fact; render placeholders'
EXECUTE AS CALLER
AS
$$
import json, re

PH = re.compile(r"\{\{\s*(F\d+)\s*\}\}")
NUM = re.compile(r"[$€£]?\d[\d,.]*\s*(?:%|[KMB]\b|x\b)?")

def run(session, doc_id, draft):
    meta = session.sql("SELECT DOC_TYPE, SUBJECT_ID, AUDIENCE FROM TRULINE.APP.DOCUMENTS WHERE DOC_ID = ? AND CHECK_STATUS = 'FACTS_READY'",
                       params=[doc_id]).collect()
    if not meta:
        return {"status": "FAIL", "violations": [{"type": "unknown_document", "detail": doc_id}]}
    audience = meta[0]["AUDIENCE"]
    facts = {r["FACT_ID"]: r for r in session.sql(
        "SELECT FACT_ID, DISPLAY, TEXT_VALUE, INTERNAL_ONLY FROM TRULINE.APP.DOC_FACTS WHERE DOC_ID = ?", params=[doc_id]).collect()}
    violations = []
    used = []
    for fid in PH.findall(draft):
        if fid not in facts:
            violations.append({"type": "unknown_fact", "detail": fid})
        elif audience == "partner" and facts[fid]["INTERNAL_ONLY"]:
            violations.append({"type": "internal_fact_in_partner_document", "detail": fid})
        used.append(fid)
    rest = PH.sub(" ", draft)
    for f in facts.values():
        if f["TEXT_VALUE"]:
            rest = re.sub(re.escape(f["TEXT_VALUE"]), " ", rest, flags=re.I)
    rest = re.sub(r"(?m)^\s*(?:#+\s*)?\d+[.)]\s", " ", rest)
    for m in NUM.finditer(rest):
        ctx = rest[max(0, m.start() - 40): m.end() + 40].replace("\n", " ").strip()
        violations.append({"type": "uncited_number", "detail": m.group(0).strip(), "context": ctx})
    rendered = PH.sub(lambda m: f"{facts[m.group(1)]['DISPLAY']} [{m.group(1)}]" if m.group(1) in facts else f"[{m.group(1)}?]", draft)
    status = "PASS" if not violations else "FAIL"
    session.sql("INSERT INTO TRULINE.CORE.DOCUMENTS (DOC_ID, DOC_TYPE, SUBJECT_ID, AUDIENCE, DRAFT, RENDERED, CHECK_STATUS, VIOLATIONS) "
                "SELECT ?, ?, ?, ?, ?, ?, ?, PARSE_JSON(?)",
                params=[doc_id, meta[0]["DOC_TYPE"], meta[0]["SUBJECT_ID"], audience, draft, rendered, status, json.dumps(violations)]).collect()
    session.sql("INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS) SELECT ?, 'DOCUMENT', ?, PARSE_JSON(?)",
                params=["CLAIM_CHECK_" + status, doc_id,
                        json.dumps({"violations": violations[:20], "facts_cited": len(set(used))})]).collect()
    return {"doc_id": doc_id, "status": status, "violations": violations, "facts_cited": sorted(set(used), key=lambda x: int(x[1:])),
            "rendered": rendered}
$$;

-- Full pipeline: facts -> Claude draft with placeholders -> claim check + label-consistency check (one repair attempt) -> rendered document.
CREATE OR REPLACE PROCEDURE GENERATE_DOC(DOC_TYPE VARCHAR, SUBJECT_ID VARCHAR, AUDIENCE VARCHAR, MODEL VARCHAR)
RETURNS VARIANT LANGUAGE PYTHON RUNTIME_VERSION = '3.11' PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'run' COMMENT = 'Generate a cited document (partner brief, partner-shareable review, weekly plan summary, monthly report)'
EXECUTE AS CALLER
AS
$$
import json, re

KINDS = {
    ("PARTNER", "internal"): ("Strategic partner brief for the Truline PAM",
                              "Summary; Retention and risk; Products and credits; Plays to run this week; What to watch"),
    ("PARTNER", "partner"): ("Partner business review to share with the partner's leadership",
                             "Highlights; Customer health; Products and credits; Recommended actions for your reps"),
    ("PARTNER_MONTHLY", "partner"): ("Monthly partner report for a reseller without a Truline PAM",
                                     "This month in brief; Customers to call; Growth opportunities"),
    ("PAM_PORTFOLIO", "internal"): ("Weekly delegation plan summary for a shared PAM",
                                    "Headline; Plays to approve; Where you are needed; Watch list"),
}

def ask(session, model, prompt):
    out = session.sql("CALL TRULINE.APP.LLM_COMPLETE(?, ?)", params=[model, prompt]).collect()[0][0]
    try:
        return json.loads(out) if out.startswith('"') else out
    except Exception:
        return out

def label_check(session, model, draft, facts):
    labels = {f["id"]: f"{f['display']} = {f['label']}" for f in facts}
    shown = re.sub(r"\{\{\s*(F\d+)\s*\}\}", lambda m: f"[{m.group(1)}: {labels.get(m.group(1), '?')}]", draft)
    prompt = f"""Each bracket [F#: value = meaning] in the text below is a cited fact and its exact meaning.
List every place where the sentence describes a fact as something other than its stated meaning
(wrong metric, wrong entity, wrong time period, or a causal claim the facts do not support).
Reply with JSON only: {{"misused": [{{"fact": "F#", "why": "..."}}]}}. Reply {{"misused": []}} if all uses are faithful.

TEXT:
{shown}"""
    out = ask(session, model, prompt)
    try:
        return json.loads(out[out.index("{"): out.rindex("}") + 1]).get("misused", [])
    except Exception:
        return []

def run(session, doc_type, subject_id, audience, model):
    doc_type, audience, model = doc_type.upper(), (audience or "internal").lower(), model or "claude-sonnet-4-5"
    kind = KINDS.get((doc_type, audience))
    if not kind:
        return {"error": f"unsupported doc_type/audience: {doc_type}/{audience}"}
    built = json.loads(session.call("TRULINE.APP.BUILD_FACTS", doc_type, subject_id, audience))
    if "error" in built:
        return built
    fact_lines = "\n".join(f"{f['id']}: {f['label']} = {f['display']}" for f in built["facts"])
    prompt = f"""You write for Truline, a design-software vendor that sells through reseller partners.
Write a {kind[0]} in Markdown with these sections: {kind[1]}.
Keep it under 250 words, concrete and action-oriented.

FACTS (the only numbers you may use):
{fact_lines}

RULES
- Write every number ONLY as its placeholder, e.g. {{{{F3}}}}. Never type digits yourself: no years, counts, ranks, percentages or amounts.
- Names (accounts, partners, reps, play types) may be written as given in the facts.
- Do not invent facts, causes or numbers. If something is not in the facts, do not mention it.
- Do not number list items; use bullets."""
    draft = ask(session, model, prompt)
    check = json.loads(session.call("TRULINE.APP.CHECK_CLAIMS", built["doc_id"], draft))
    misused = label_check(session, model, draft, built["facts"]) if check["status"] == "PASS" else []
    attempts = 1
    if check["status"] == "FAIL" or misused:
        issues = check["violations"][:10] + [{"type": "fact_misused", **m} for m in misused[:10]]
        fix = prompt + f"\n\nYour previous draft broke the rules: {json.dumps(issues)}\nRewrite it fixing every issue.\n\nPrevious draft:\n{draft}"
        draft = ask(session, model, fix)
        check = json.loads(session.call("TRULINE.APP.CHECK_CLAIMS", built["doc_id"], draft))
        misused = label_check(session, model, draft, built["facts"]) if check["status"] == "PASS" else []
        attempts = 2
    status = check["status"] if check["status"] == "FAIL" or not misused else "PASS_WITH_WARNINGS"
    session.sql("INSERT INTO TRULINE.CORE.AUDIT_LOG (ACTION, OBJECT_TYPE, OBJECT_ID, DETAILS) SELECT 'GENERATE_DOC', 'DOCUMENT', ?, PARSE_JSON(?)",
                params=[built["doc_id"], json.dumps({"doc_type": doc_type, "subject_id": built["subject_id"], "audience": audience,
                                                     "model": model, "attempts": attempts, "status": status, "misused": misused})]).collect()
    return {"doc_id": built["doc_id"], "status": status, "attempts": attempts, "violations": check["violations"], "misused": misused,
            "rendered": check["rendered"], "draft": draft, "facts": built["facts"]}
$$;
