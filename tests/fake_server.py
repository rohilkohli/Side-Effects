"""Run the app locally with the Gemini stand-in, for UI work without credentials.

    python -m tests.fake_server   ->  http://localhost:8080
"""
import time

import uvicorn

from app import bq, gemini, live, voice
from app.agents import assistant, pharmacist, shopper
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


def _slow_assistant(*a, **kw):
    time.sleep(0.6)
    return fakes.fake_assistant_turn(*a, **kw)


assistant._turn = _slow_assistant
voice.transcribe = lambda audio, mime: "Is Klarna risky if my income is irregular?"

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
def _fake_cfpb(params):
    base = "date_received_max" in params
    pay = 40 if base else 12
    if params.get("company") in ("SYNCHRONY FINANCIAL", "Klarna AB") and not base:
        pay = 140  # a made-up spike in payment problems, so the safety-alert scan has something to find
    time.sleep(0.3)
    return {"hits": {"total": {"value": (800 if base else 230) + pay}, "hits": [{"_source": {"date_received": "2026-10-09T18:11:45.000Z"}}]},
            "aggregations": {"issue": {"issue": {"buckets": [
                {"key": "Problem with a purchase shown on your statement", "doc_count": 400 if base else 120},
                {"key": "Incorrect information on your report", "doc_count": 250 if base else 70},
                {"key": "Managing an account", "doc_count": 150 if base else 40},
                {"key": "Problem when making payments", "doc_count": pay}]}}}}


live._cfpb = _fake_cfpb
live._suggest = lambda text: ["UPSTART NETWORK, INC.", "UPSTART HOLDINGS"] if "upstart" in text.lower() else []
live.grounded = lambda prompt: (time.sleep(1.0) or "Stand-in note: a payments system migration was reported in the news.",
                                [{"title": "stand-in.example", "url": "https://example.com/"}], [])
live._grounded_research = lambda name, company, product_type: (
    "Stand-in research note about " + name, [{"title": "stand-in.example", "url": "https://example.com/"}], ["stand-in query"])


if __name__ == "__main__":
    uvicorn.run("app.main:app", port=8080)
