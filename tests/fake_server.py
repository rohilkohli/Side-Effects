"""Run the app locally with the Gemini stand-in, for UI work without credentials.

    python -m tests.fake_server   ->  http://localhost:8080
"""
import time

import uvicorn

from app import bq, gemini, live
from app.agents import pharmacist, shopper
from tests import fakes



def _slow_fake(prompt, schema, **kw):
    if schema.__name__ in ("Attack", "GuardianReport", "ThemeReport"):
        time.sleep(1.2)
    return fakes.fake(prompt, schema, **kw)


gemini.generate_json = _slow_fake


def _slow_turn(*a, **kw):
    time.sleep(0.8)  # roughly a real model step, so the screen streams like the live demo
    return fakes.fake_shopper_turn(*a, **kw)


shopper._model_turn = _slow_turn

# Made-up BigQuery answers, only so the BigQuery panels can be seen locally.
bq.lender_snapshot = lambda company, product_type="credit_card": {
    "available": True, "company": company, "source": bq.PUBLIC_TABLE, "latest_date": "2026-09-30",
    "last_12_months": 1234, "top_issues": [{"issue": "Problem with a purchase shown on your statement", "n": 412},
                                           {"issue": "Fees or interest", "n": 230}, {"issue": "Getting a credit card", "n": 118}]}
bq.audit_summary = lambda: {"available": True, "table": "demo.side_effects.gate_decisions", "total": 42, "held": 17, "disclosed": 9,
                            "recent": [{"ts": "2026-10-18T05:30:00Z", "source": "checkout", "lender": "SYNCHRONY FINANCIAL", "verdict": "human_review"},
                                       {"ts": "2026-10-18T05:29:10Z", "source": "api", "lender": "Klarna", "verdict": "disclose"}]}

pharmacist.answer = lambda leaflet, pages, history, question: (
    "Stand-in answer for local testing: on the real site, Gemini answers from this leaflet, the contract and real complaints.")

# Made-up live answers (no network here), only so the live check on the leaflet can be seen locally.
live._cfpb = lambda params: ({"hits": {"total": {"value": 1180 if "date_received_max" in params else 1527}, "hits": [
    {"_source": {"date_received": "2026-10-09T18:11:45.000Z"}}]},
    "aggregations": {"issue": {"issue": {"buckets": [{"key": "Problem with a purchase shown on your statement", "doc_count": 576},
                                                      {"key": "Incorrect information on your report", "doc_count": 217},
                                                      {"key": "Managing an account", "doc_count": 152}]}}}})
live._grounded_research = lambda name, company, product_type: (
    "Stand-in research note about " + name, [{"title": "stand-in.example", "url": "https://example.com/"}], ["stand-in query"])


if __name__ == "__main__":
    uvicorn.run("app.main:app", port=8080)
