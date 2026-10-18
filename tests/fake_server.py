"""Run the app locally with the Gemini stand-in, for UI work without credentials.

    python -m tests.fake_server   ->  http://localhost:8080
"""
import time

import uvicorn

from app import bq, gemini
from app.agents import shopper
from tests import fakes

gemini.generate_json = fakes.fake


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

if __name__ == "__main__":
    uvicorn.run("app.main:app", port=8080)
