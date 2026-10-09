"""End-to-end tests with Gemini replaced by a stand-in that returns fixed, schema-valid answers.

The stand-in lets the statistics, quote verification, API and streaming be
tested without credentials; it does not test Gemini's judgement (see
pipeline/eval_classifier.py for that).
"""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import evidence, gemini, pipeline
from app.agents import clauses
from app.main import app
from tests import fakes
from tests.fakes import FAKE_QUOTE, REAL_QUOTE

SAMPLES = Path(__file__).parent.parent / "samples"


@pytest.fixture
def fake_gemini(monkeypatch):
    monkeypatch.setattr(gemini, "generate_json", fakes.fake)


def test_resolve_brands():
    assert evidence.resolve_company("Apple Card") == "GOLDMAN SACHS BANK USA"
    assert evidence.resolve_company("Pay over time with Affirm") == "Affirm Holdings, Inc"
    assert evidence.resolve_company("Example Lending Co.") is None


def test_goldman_dispute_signal_matches_enforcement():
    """The CFPB fined Goldman $45M in Oct 2024 over Apple Card disputes; the signal must be there."""
    lines = evidence.signals_for("GOLDMAN SACHS BANK USA", "credit_card")["lines"]
    dispute = [l for l in lines if l["label"] == "Purchase disputes left unresolved"]
    assert dispute and dispute[0]["reported_x"] >= 2 and dispute[0]["status"] == "persisting"
    assert dispute[0]["scope"] == "bank"


def test_bnpl_gets_product_class_signal():
    lines = evidence.signals_for(None, "bnpl")["lines"]
    assert any(l["scope"] == "product_class" and l["reported_x"] >= 3 for l in lines)


def test_quote_must_be_verbatim():
    pages = pipeline.pages_from_text((SAMPLES / "fictional-bnpl-agreement.txt").read_text())
    assert len(pages) == 6
    assert clauses.locate(REAL_QUOTE, pages) == 4
    assert clauses.locate(FAKE_QUOTE, pages) is None


def test_pipeline_end_to_end(fake_gemini):
    inp = pipeline.Inputs(flyer_text=(SAMPLES / "fictional-bnpl-flyer.txt").read_text(),
                          contract_text=(SAMPLES / "fictional-bnpl-agreement.txt").read_text(),
                          profile=["irregular_income"])
    events = list(pipeline.run(inp))
    lf = events[-1]["leaflet"]
    assert lf["product"]["matched_company"] is None
    assert all(l["scope"] == "product_class" for l in lf["side_effects"])
    linked = [l for l in lf["side_effects"] if l.get("clause")]
    assert len(linked) == 1 and linked[0]["clause"]["page"] == 2  # page corrected from the model's 99
    assert lf["rejected_quotes"] == 1  # the invented quote was thrown away
    assert lf["contract_only"][0]["page"] == 4
    assert [c["condition"] for c in lf["contraindications"]] == ["Not suitable if your income is irregular"]
    assert "contract only" in lf["coverage"]


def test_api_stream_and_agent_check(fake_gemini):
    client = TestClient(app)
    r = client.post("/api/leaflet", data={"flyer_text": "Apple Card. Get 3% Daily Cash.", "issuer": "Apple Card",
                                          "product_type": "credit_card"})
    events = [json.loads(x) for x in r.text.strip().splitlines()]
    assert [e["step"] for e in events][-1] == "leaflet"
    lf = events[-1]["leaflet"]
    assert lf["product"]["matched_company"] == "GOLDMAN SACHS BANK USA"
    assert client.get(f"/api/v1/leaflets/{lf['id']}").status_code == 200

    check = client.post("/api/v1/check", json={"issuer": "Apple Card", "product_type": "credit_card",
                                                "applicant_profile": ["big_purchase"]}).json()
    assert check["verdict"] == "human_review"
    assert "Purchase disputes left unresolved" in check["matches_applicant_situation"]
    assert client.post("/api/v1/check", json={"issuer": "Nobody Bank"}).json()["verdict"] == "no_signal"


def test_without_credentials_the_ui_gets_a_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    gemini.client.cache_clear()
    r = TestClient(app).post("/api/leaflet", data={"flyer_text": "0% APR"})
    assert "not configured" in r.text.splitlines()[-1]


def test_india_rates_from_rbi():
    le = evidence.local_evidence("IN", "credit_card", "AU Small Finance Bank LIT card")
    assert le["group"]["label"] == "Small finance banks" and le["group"]["x_vs_india"] == 3.0
    assert evidence.india_group("SBI Card ELITE") == "nbfc"
    assert evidence.local_evidence("US", "credit_card", "AU Bank") is None
    india = evidence.apac()["IN"]
    assert 105e6 < india["cards_in_force"] < 115e6  # matches ~110M Indian credit cards, March 2025


def test_india_bank_disclosure():
    assert evidence.india_disclosure("American Express Platinum")["bank"] == "American Express Banking Corp"
    assert evidence.india_disclosure("SBI Card ELITE") is None  # SBI Card is not SBI
    le = evidence.local_evidence("IN", "personal_loan", "DCB Bank personal loan")
    assert le["disclosure"]["bank"] == "DCB Bank" and le["groups"] == []
