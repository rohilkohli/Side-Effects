-- Harvest at scale: Gemini codes every CFPB complaint story inside BigQuery.
-- Source: the public CFPB complaint table. Cost estimate from the stress test: about $27-61
-- for 200k stories with a Flash-Lite model. Replace PROJECT and the connection name.
-- Not yet run: this environment had no Google Cloud credentials.

-- 1. One-time: a remote model that points at Gemini on Vertex AI.
CREATE OR REPLACE MODEL `PROJECT.side_effects.gemini_coder`
  REMOTE WITH CONNECTION `PROJECT.us.vertex_ai`
  OPTIONS (ENDPOINT = 'gemini-3.5-flash-lite');

-- 2. Code each narrative. The prompt carries the vocabulary (data/vocabulary.json).
CREATE OR REPLACE TABLE `PROJECT.side_effects.coded_complaints` AS
SELECT
  complaint_id,
  company_name,
  product,
  issue,
  subissue,
  date_received,
  JSON_VALUE(ml_generate_text_llm_result, '$.primary') AS primary_code,
  JSON_VALUE_ARRAY(ml_generate_text_llm_result, '$.codes') AS codes,
  SAFE_CAST(JSON_VALUE(ml_generate_text_llm_result, '$.is_template') AS BOOL) AS is_template
FROM ML.GENERATE_TEXT(
  MODEL `PROJECT.side_effects.gemini_coder`,
  (
    SELECT complaint_id, company_name, product, issue, subissue, date_received,
      CONCAT(
        'Code this consumer complaint into the financial side-effect vocabulary. ',
        'Answer only with JSON {"is_template": bool, "codes": [..], "primary": ".."}. ',
        'Vocabulary: ', (SELECT STRING_AGG(CONCAT(code, ' ', preferred_term, ': ', definition), '; ')
                         FROM `PROJECT.side_effects.vocabulary`),
        '\nCOMPLAINT: ', consumer_complaint_narrative) AS prompt
    FROM `bigquery-public-data.cfpb_complaints.complaint_database`
    WHERE consumer_complaint_narrative IS NOT NULL
      AND product IN ('Credit card', 'Credit card or prepaid card',
                      'Payday loan, title loan, personal loan, or advance loan')
      AND date_received >= '2023-01-01'
  ),
  STRUCT(1024 AS max_output_tokens, TRUE AS flatten_json_output,
         'application/json' AS response_mime_type)
);
