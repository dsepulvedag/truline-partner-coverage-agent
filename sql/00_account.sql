-- Account-level settings (run once as ACCOUNTADMIN, before the other files).
USE ROLE ACCOUNTADMIN;

-- Claude models in AI_COMPLETE / Cortex Agents may be served from another region.
ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';

-- Lets the Cortex Agent's web search tool run ("why now"; it searches company name and domain only).
ALTER ACCOUNT SET ENABLE_CORTEX_WEBSEARCH = TRUE;
