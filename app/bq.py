"""BigQuery, used two ways at runtime:

1. Live lookups: the latest complaint counts for a lender, straight from Google's
   public copy of the CFPB Consumer Complaint Database.
2. Audit trail: every decision the agent gate makes is written to a table, so a
   bank or regulator can see what agents were allowed to sign and what was held.

Both are optional. If BigQuery is switched off or fails, the app carries on and
the page simply hides the BigQuery panels; the gate's verdict never depends on it.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

log = logging.getLogger("side_effects.bq")

PUBLIC_TABLE = "bigquery-public-data.cfpb_complaints.complaint_database"
DATASET = os.environ.get("BQ_DATASET", "side_effects")
AUDIT_TABLE = "gate_decisions"
MAX_BYTES = 3 * 1024**3  # refuse any query that would scan more than 3 GB
CACHE_SECONDS = 6 * 3600
PRODUCT_FILTER = {"credit_card": "Credit card%"}  # other products: all of the lender's complaints

_client = None
_lock = threading.Lock()
_cache: dict[tuple, tuple[float, dict]] = {}
_pool = ThreadPoolExecutor(max_workers=2)


def enabled() -> bool:
    return os.environ.get("BIGQUERY_ENABLED", "").lower() == "true" and bool(os.environ.get("GOOGLE_CLOUD_PROJECT"))


def client():
    global _client
    with _lock:
        if _client is None:
            from google.cloud import bigquery
            _client = bigquery.Client(project=os.environ["GOOGLE_CLOUD_PROJECT"])
        return _client


def _query(sql: str, params: list) -> list[dict]:
    from google.cloud import bigquery
    cfg = bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=MAX_BYTES, use_query_cache=True)
    job = client().query(sql, job_config=cfg)
    return [dict(r) for r in job.result(timeout=20)]


LENDER_SQL = f"""
WITH latest AS (SELECT MAX(date_received) AS d FROM `{PUBLIC_TABLE}`),
recent AS (
  SELECT issue FROM `{PUBLIC_TABLE}`, latest
  WHERE company_name = @company AND product LIKE @product
    AND date_received > DATE_SUB(latest.d, INTERVAL 365 DAY)
)
SELECT
  (SELECT d FROM latest) AS latest_date,
  (SELECT COUNT(*) FROM recent) AS last_12_months,
  ARRAY(SELECT AS STRUCT issue, COUNT(*) AS n FROM recent GROUP BY issue ORDER BY n DESC LIMIT 3) AS top_issues
"""


def lender_snapshot(company: str, product_type: str = "credit_card") -> dict:
    """Latest 12 months of complaints about one lender, queried live from BigQuery."""
    if not enabled() or not company:
        return {"available": False}
    key = (company, product_type)
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1] | {"cached": True}
    from google.cloud import bigquery
    try:
        rows = _query(LENDER_SQL, [
            bigquery.ScalarQueryParameter("company", "STRING", company),
            bigquery.ScalarQueryParameter("product", "STRING", PRODUCT_FILTER.get(product_type, "%")),
        ])
    except Exception as e:  # BigQuery is an extra; never break the page for it
        log.warning("BigQuery lender lookup failed: %s", e)
        return {"available": False}
    r = rows[0] if rows else {}
    out = {
        "available": True,
        "company": company,
        "source": PUBLIC_TABLE,
        "latest_date": str(r.get("latest_date") or ""),
        "last_12_months": int(r.get("last_12_months") or 0),
        "top_issues": [{"issue": i["issue"], "n": int(i["n"])} for i in (r.get("top_issues") or [])],
    }
    _cache[key] = (time.time(), out)
    return out


def _audit_ref() -> str:
    return f"{os.environ['GOOGLE_CLOUD_PROJECT']}.{DATASET}.{AUDIT_TABLE}"


def log_decision(source: str, issuer: str, product_type: str, profile: list[str], result: dict) -> None:
    """Write one gate decision to the audit table in the background. Never raises."""
    if not enabled():
        return
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "issuer": issuer,
        "issuer_matched": result.get("issuer_matched"),
        "product_type": product_type,
        "applicant_profile": list(profile or []),
        "verdict": result.get("verdict"),
        "matches": list(result.get("matches_applicant_situation") or []),
        "disclosures": len(result.get("required_disclosures") or []),
    }

    def write():
        try:
            errors = client().insert_rows_json(_audit_ref(), [row])
            if errors:
                log.warning("BigQuery audit insert errors: %s", errors)
        except Exception as e:
            log.warning("BigQuery audit insert failed: %s", e)

    _pool.submit(write)


AUDIT_SQL = """
SELECT
  COUNT(*) AS total,
  COUNTIF(verdict = 'human_review') AS held,
  COUNTIF(verdict = 'disclose') AS disclosed,
  ARRAY_AGG(STRUCT(ts, source, issuer_matched, verdict) ORDER BY ts DESC LIMIT 5) AS recent
FROM `{table}`
WHERE ts > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
"""


def audit_summary() -> dict:
    """What the gate decided over the last 30 days, read back from BigQuery."""
    if not enabled():
        return {"available": False}
    try:
        rows = _query(AUDIT_SQL.format(table=_audit_ref()), [])
    except Exception as e:
        log.warning("BigQuery audit read failed: %s", e)
        return {"available": False}
    r = rows[0] if rows else {}
    return {
        "available": True,
        "table": _audit_ref(),
        "total": int(r.get("total") or 0),
        "held": int(r.get("held") or 0),
        "disclosed": int(r.get("disclosed") or 0),
        "recent": [{"ts": str(x["ts"]), "source": x["source"], "lender": x["issuer_matched"], "verdict": x["verdict"]}
                   for x in (r.get("recent") or [])],
    }
