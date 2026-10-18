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


def test_a_typed_name_alone_makes_a_leaflet(fake_gemini):
    seen = {}
    real = fakes.fake

    def spy(prompt, schema, **kw):
        if schema.__name__ == "ProductCard":
            seen["prompt"] = prompt
        return real(prompt, schema, **kw)

    gemini.generate_json = spy
    events = list(pipeline.run(pipeline.Inputs(issuer_override="Apple Card")))
    assert events[-1]["step"] == "leaflet"
    assert "Apple Card" in seen["prompt"][0]  # Gemini is told only the name was typed
    assert events[-1]["leaflet"]["product"]["matched_company"] == "GOLDMAN SACHS BANK USA"
    assert events[1]["detail"].startswith("Found ")
    assert list(pipeline.run(pipeline.Inputs()))[-1]["status"] == "error"


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


def _agent(client, persona, gated):
    r = client.post("/api/agent/run", json={"persona": persona, "gated": gated})
    return [json.loads(x) for x in r.text.strip().splitlines()]


def test_agent_without_gate_signs_up_blind(monkeypatch):
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", fakes.fake_shopper_turn)
    events = _agent(TestClient(app), "maya", gated=False)
    order = events[-1]
    assert order["type"] == "order" and order["offer"]["id"] == "store_card" and not order["confirmed_by_person"]
    assert any(d["matches"] and d["side_effect"] == "Interest rate rises unexpectedly" for d in order["unseen_side_effects"])
    assert not any(e["type"] == "check" for e in events)


def test_agent_with_gate_stops_and_asks(monkeypatch):
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", fakes.fake_shopper_turn)
    client = TestClient(app)
    events = _agent(client, "maya", gated=True)
    checks = [e for e in events if e["type"] == "check"]
    assert len(checks) == 3 and all(c["result"]["verdict"] == "human_review" for c in checks)
    assert events[-1]["type"] == "ask" and not any(e["type"] == "order" for e in events)
    assert any(e["type"] == "thought" for e in events)
    done = client.post("/api/agent/confirm", json={"persona": "maya", "offer_id": "affirm_12"}).json()
    assert done["confirmed_by_person"] and done["disclosures_shown"]


def test_gate_holds_even_if_agent_skips_the_check(monkeypatch):
    """The gate lives in place_order, so an agent that ignores its instructions still cannot sign."""
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", lambda c, s, t: fakes.fake_shopper_turn(c, s, t, skip_check=True))
    events = _agent(TestClient(app), "maya", gated=True)
    assert any(e["type"] == "blocked" and e["offer"]["id"] == "store_card" for e in events)
    assert not any(e["type"] == "order" for e in events)
    assert events[-1]["type"] == "ask"


def test_agent_shops_for_a_person_described_in_their_own_words(monkeypatch, fake_gemini):
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", fakes.fake_shopper_turn)
    client = TestClient(app)
    me = client.post("/api/agent/read-person", json={"text": "I'm Priya, a student with a part-time job and a phone on EMI"}).json()
    assert me["name"] == "Priya" and me["profile"] == ["irregular_income", "other_bnpl"]
    r = client.post("/api/agent/run", json={"gated": True, "custom": me | {"profile": me["profile"] + ["made_up"]}})
    events = [json.loads(x) for x in r.text.strip().splitlines()]
    assert events[0]["persona"]["name"] == "Priya"
    assert events[-1]["type"] == "ask"


def test_hacked_store_cannot_talk_its_way_past_the_gate(monkeypatch):
    """The checkout page tells AI agents the store card is approved; the gate still refuses."""
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", lambda c, s, t: fakes.fake_shopper_turn(c, s, t, skip_check=True))
    client = TestClient(app)
    gated = [json.loads(x) for x in client.post("/api/agent/run", json={"persona": "maya", "gated": True, "hacked": True}).text.strip().splitlines()]
    assert any(e["type"] == "injection" for e in gated)
    assert any(e["type"] == "blocked" for e in gated) and not any(e["type"] == "order" for e in gated)
    plain = [json.loads(x) for x in client.post("/api/agent/run", json={"persona": "maya", "gated": False, "hacked": True}).text.strip().splitlines()]
    assert plain[-1]["type"] == "order" and not any(e["type"] == "injection" for e in plain)


# ---- BigQuery: optional, never in the gate's way ----

from app import bq


class _SyncPool:
    def submit(self, fn):
        fn()


class _FakeBQ:
    def __init__(self):
        self.inserted = []

    def insert_rows_json(self, table, rows):
        self.inserted.append((table, rows))
        return []


def _bq_on(monkeypatch):
    monkeypatch.setenv("BIGQUERY_ENABLED", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "demo-project")
    fake = _FakeBQ()
    monkeypatch.setattr(bq, "_client", fake)
    monkeypatch.setattr(bq, "_pool", _SyncPool())
    bq._cache.clear()
    return fake


def test_bigquery_off_hides_panels_and_gate_still_works(monkeypatch):
    monkeypatch.delenv("BIGQUERY_ENABLED", raising=False)
    c = TestClient(app)
    assert c.get("/api/bigquery/lender", params={"issuer": "Apple Card"}).json() == {"available": False}
    assert c.get("/api/bigquery/audit").json() == {"available": False}
    assert c.post("/api/v1/check", json={"issuer": "Klarna", "product_type": "bnpl"}).status_code == 200


def test_every_gate_decision_is_written_to_the_audit_table(monkeypatch):
    fake = _bq_on(monkeypatch)
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", fakes.fake_shopper_turn)
    c = TestClient(app)
    c.post("/api/v1/check", json={"issuer": "Klarna", "product_type": "bnpl", "applicant_profile": ["irregular_income"]})
    list(shopper.run("maya", gated=True))
    rows = [r for _, rs in fake.inserted for r in rs]
    assert all(t == "demo-project.side_effects.gate_decisions" for t, _ in fake.inserted)
    assert rows[0]["source"] == "api" and rows[0]["verdict"] == "human_review"
    assert any(r["source"] == "agent_check" for r in rows)


def test_bigquery_lender_snapshot_and_failure(monkeypatch):
    _bq_on(monkeypatch)
    calls = []

    def fake_query(sql, params):
        calls.append(params)
        return [{"latest_date": "2026-09-30", "last_12_months": 1234,
                 "top_issues": [{"issue": "Problem with a purchase shown on your statement", "n": 400}]}]

    monkeypatch.setattr(bq, "_query", fake_query)
    c = TestClient(app)
    d = c.get("/api/bigquery/lender", params={"issuer": "Apple Card"}).json()
    assert d["available"] and d["last_12_months"] == 1234 and d["company"]
    c.get("/api/bigquery/lender", params={"issuer": "Apple Card"})
    assert len(calls) == 1  # cached

    def broken(sql, params):
        raise RuntimeError("quota")

    monkeypatch.setattr(bq, "_query", broken)
    bq._cache.clear()
    assert c.get("/api/bigquery/lender", params={"issuer": "Apple Card"}).json() == {"available": False}
    assert c.get("/api/bigquery/audit").json() == {"available": False}


# ---- Scam arena and emerging side effects ----

def test_scam_arena_adapts_verifies_quotes_and_gate_holds(monkeypatch, fake_gemini):
    from app.agents import shopper
    monkeypatch.setattr(shopper, "_model_turn", fakes.fake_shopper_turn)
    lines = TestClient(app).post("/api/arena/run").text.strip().splitlines()
    events = [json.loads(l) for l in lines]
    attacks = [e for e in events if e["type"] == "attack"]
    assert len(attacks) == 3 and attacks[0]["attack"]["technique"] != attacks[1]["attack"]["technique"]
    g1 = next(e for e in events if e["type"] == "guardian")
    assert g1["caught"] and g1["rejected_quotes"] == 1  # the quote that is not on the page is thrown out
    assert all(f["quote"] in json.dumps(attacks[0]) for f in g1["findings"])
    gates = [e for e in events if e["type"] == "gate"]
    assert all(g["held"] for g in gates)
    assert events[-1]["type"] == "arena_end" and events[-1]["score"]["gate_held"] == 3


def test_scam_page_reaches_the_agent():
    from app.agents import arena, shopper
    atk = {"technique": "false_urgency", "target_offer_id": "affirm_12", "banner": "Only today", "added_terms": "Hurry."}
    page = arena.page_text(atk)
    assert "Only today" in page and "Hurry." in page
    assert [o for o in shopper.shown_offers(False, atk) if o["id"] == "affirm_12"][0]["terms"].endswith("Hurry.")


def test_emerging_side_effects_only_count_real_ids_and_quotes(fake_gemini):
    d = TestClient(app).get("/api/radar", params={"issuer": "Synchrony"}).json()
    assert d["available"] and "stored sample" in d["source"]
    first, second = d["themes"]
    assert first["count"] == 3  # the made-up id is not counted
    assert first["quote"] and second["quote"] == ""  # a quote not in any story is dropped
    assert TestClient(app).get("/api/radar", params={"issuer": "Nobody Bank Ltd"}).json()["available"] is False


def test_scam_arena_keeps_going_when_gemini_fails(monkeypatch):
    """Attacker refuses, guardian errors: every round still finishes and the gate still decides."""
    from app.agents import arena, shopper
    from app.schemas import Attack, GuardianReport

    def flaky(prompt, schema, **kw):
        if schema in (Attack, GuardianReport):
            raise gemini.LLMEmpty("blocked")
        return fakes.fake(prompt, schema, **kw)

    monkeypatch.setattr(gemini, "generate_json", flaky)
    monkeypatch.setattr(shopper, "_model_turn", fakes.fake_shopper_turn)
    events = list(arena.run())
    attacks = [e for e in events if e["type"] == "attack"]
    assert len(attacks) == 3 and all(a["attack"]["source"] == "playbook" for a in attacks)
    assert len({a["attack"]["technique"] for a in attacks}) == 3
    assert all(e.get("error") for e in events if e["type"] == "guardian")
    assert [e for e in events if e["type"] == "gate"] and events[-1]["type"] == "arena_end"


def test_scam_that_changes_the_agents_choice_counts_as_fooled(monkeypatch, fake_gemini):
    from app.agents import arena, shopper

    def swayed(contents, system, tools, **kw):
        from google.genai import types
        done = [p.function_response.name for c in contents for p in (c.parts or []) if p.function_response]
        if not done:
            return types.Content(role="model", parts=[types.Part.from_function_call(name="search_payment_options", args={})])
        return types.Content(role="model", parts=[types.Part.from_text(text="The page says Klarna is pre-approved."),
                                                  types.Part.from_function_call(name="place_order", args={"offer_id": "klarna_pay4"})])

    monkeypatch.setattr(shopper, "_model_turn", swayed)
    events = list(arena.run(rounds=1))
    agent = next(e for e in events if e["type"] == "agent")
    gate = next(e for e in events if e["type"] == "gate")
    assert agent["fooled"] and gate["held"]


# ---- Live check ----

def test_live_check_reads_the_cfpb_feed_and_trend(monkeypatch):
    from app import live
    live._cache.clear()
    calls = []

    def fake_cfpb(params):
        calls.append(params)
        n = 100 if "date_received_max" in params else 150
        return {"hits": {"total": {"value": n}, "hits": [{"_source": {"date_received": "2026-10-09T18:11:45.000Z"}}]},
                "aggregations": {"issue": {"issue": {"buckets": [{"key": "Managing an account", "doc_count": 40}]}}}}

    monkeypatch.setattr(live, "_cfpb", fake_cfpb)
    d = TestClient(app).get("/api/live/check", params={"name": "Apple Card"}).json()
    c = d["complaints"]
    assert d["company"] == "GOLDMAN SACHS BANK USA" and calls[0]["company"] == "GOLDMAN SACHS BANK USA"
    assert c["last_90_days"] == 150 and c["previous_90_days"] == 100 and c["change_pct"] == 50
    assert c["latest_complaint"] == "2026-10-09" and c["top_issues"][0]["n"] == 40


def test_live_check_survives_a_dead_feed_and_unknown_names(monkeypatch):
    from app import live
    live._cache.clear()

    def down(params):
        raise OSError("timeout")

    monkeypatch.setattr(live, "_cfpb", down)
    c = TestClient(app)
    assert c.get("/api/live/check", params={"name": "Apple Card"}).json()["complaints"]["available"] is False
    unknown = c.get("/api/live/check", params={"name": "Totally Made Up Lender Zzz"}).json()
    assert unknown["company"] is None and unknown["signals"] == []


def test_live_news_is_grounded_and_structured(monkeypatch, fake_gemini):
    from app import live
    live._cache.clear()
    monkeypatch.setattr(live, "_grounded_research", lambda n, c, p: ("note", [{"title": "reuters.com", "url": "https://x"}], ["q"]))
    d = TestClient(app).get("/api/live/news", params={"name": "Apple Card"}).json()
    assert d["available"] and d["grounded"] and d["items"][0]["kind"] == "enforcement" and d["sources"][0]["title"] == "reuters.com"

    def boom(n, c, p):
        raise RuntimeError("search down")

    live._cache.clear()
    monkeypatch.setattr(live, "_grounded_research", boom)
    assert TestClient(app).get("/api/live/news", params={"name": "Apple Card"}).json()["available"] is False


def _fake_live(monkeypatch):
    from app import live
    live._cache.clear()
    monkeypatch.setattr(live, "_cfpb", lambda params: {"hits": {"total": {"value": 90 if "date_received_max" in params else 120},
                                                                 "hits": [{"_source": {"date_received": "2026-10-09"}}]},
                                                        "aggregations": {"issue": {"issue": {"buckets": []}}}})
    monkeypatch.setattr(live, "_grounded_research", lambda name, company, pt: ("note", [{"title": "s", "url": "https://example.com/"}], ["q"]))


def test_assistant_streams_each_tool_call_then_answers(monkeypatch, fake_gemini):
    from app.agents import assistant
    _fake_live(monkeypatch)
    monkeypatch.setattr(assistant, "_turn", fakes.fake_assistant_turn)
    r = TestClient(app).post("/api/assistant", json={"question": "Is Apple Card risky?", "history": []})
    events = [json.loads(x) for x in r.text.strip().splitlines()]
    kinds = [e["type"] for e in events]
    assert kinds[:3] == ["tool", "tool", "tool"]  # the lookups start together, before any result
    assert events[0]["label"] == "Checking complaints for Apple Card"
    done = {e["name"]: e["summary"] for e in events if e["type"] == "tool_done"}
    assert done["check_lender"].startswith("120 complaints in 90 days")
    assert any(e["type"] == "link" and e["url"] == "/leaflet?q=Apple Card" for e in events)
    assert events[-1]["type"] == "say" and "120 complaints" in events[-1]["text"]


def test_mcp_server_lists_and_calls_the_same_tools(monkeypatch, fake_gemini):
    _fake_live(monkeypatch)
    c = TestClient(app)
    init = c.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t"}}}).json()
    assert init["result"]["protocolVersion"] == "2025-06-18" and "tools" in init["result"]["capabilities"]
    assert c.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    tools_ = {t["name"]: t for t in c.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}).json()["result"]["tools"]}
    assert set(tools_) == {"check_lender", "lender_news", "safety_alerts", "compare_lenders", "find_alternatives", "gate_check"}
    assert tools_["gate_check"]["inputSchema"]["properties"]["applicant_profile"]["type"] == "array"
    out = c.post("/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "gate_check", "arguments": {"issuer": "Apple Card", "applicant_profile": ["big_purchase"]}}}).json()["result"]
    assert out["isError"] is False and out["structuredContent"]["verdict"] == "human_review"  # same verdict as /api/v1/check
    bad = c.post("/mcp", json={"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "nope"}}).json()
    assert bad["error"]["code"] == -32602
    assert c.get("/.well-known/side-effects.json").json()["mcp"]["path"] == "/mcp"


def test_same_lookup_at_the_same_time_runs_once(monkeypatch):
    import threading
    from app import live
    live._cache.clear()
    runs = []

    def slow():
        runs.append(1)
        threading.Event().wait(0.3)
        return {"available": True, "n": len(runs)}

    out = []
    ts = [threading.Thread(target=lambda: out.append(live._cached(("t", "x"), slow))) for _ in range(3)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert len(runs) == 1 and all(o["n"] == 1 for o in out)


def _feed(recent: dict, base: dict):
    """A stand-in CFPB feed: issue counts for the recent window and for the baseline window."""
    def fake(params):
        counts = base if "date_received_max" in params else recent
        return {"hits": {"total": {"value": sum(counts.values())}, "hits": []},
                "aggregations": {"issue": {"issue": {"buckets": [{"key": k, "doc_count": v} for k, v in counts.items()]}}}}
    return fake


def test_safety_alert_loop_detects_writes_records_and_the_gate_acts(monkeypatch, fake_gemini):
    from app import alerts, bq, gate, live
    alerts._alerts.clear(); alerts._last_scan.clear()
    written = []
    monkeypatch.setattr(bq, "insert", lambda table, row: written.append((table, row)))
    monkeypatch.setattr(live, "grounded", lambda prompt: ("A system migration in August delayed payments.", [{"title": "s", "url": "https://example.com/"}], []))
    # Payment problems jump from 5% to 30% of complaints; everything else is steady.
    monkeypatch.setattr(live, "_cfpb", _feed({"Problem when making payments": 60, "Fees or interest": 140},
                                             {"Problem when making payments": 40, "Fees or interest": 760}))
    before = gate.check("Apple Card", "credit_card", ["irregular_income"])
    events = list(alerts.scan([("GOLDMAN SACHS BANK USA", "credit_card")], force=True))
    a = next(e["alert"] for e in events if e["type"] == "alert")
    assert a["label"] == "Trouble making repayments go through" and a["ratio"] == 6.0 and a["recent_n"] == 60
    assert "irregular_income" in a["affects"] and a["sources"]  # the news found a cause, so its source is kept
    assert written and written[0][0] == "safety_alerts"
    after = gate.check("Apple Card", "credit_card", ["irregular_income"])
    assert after["safety_alerts"][0]["id"] == a["id"]
    assert "Trouble making repayments go through" in after["matches_applicant_situation"]
    assert after["verdict"] == "human_review" and len(after["required_disclosures"]) == len(before["required_disclosures"]) + 1
    # The same alert reaches the assistant's and MCP's tool, and the scan does not rerun within the hour.
    from app import tools
    assert tools.safety_alerts("Apple Card")["alerts"][0]["headline"]
    assert next(alerts.scan())["type"] == "recent"
    alerts._alerts.clear(); alerts._last_scan.clear()


def test_steady_complaints_raise_no_alert(monkeypatch):
    from app import alerts, live
    monkeypatch.setattr(live, "_cfpb", _feed({"Fees or interest": 100, "Problem when making payments": 20},
                                             {"Fees or interest": 400, "Problem when making payments": 80}))
    assert alerts.detect("GOLDMAN SACHS BANK USA", "credit_card")["signals"] == []


def test_gate_severity_and_action_follow_fixed_rules():
    from app import gate
    klarna = gate.check("Klarna", "bnpl", ["irregular_income", "other_bnpl"])
    assert klarna["verdict"] == "human_review" and klarna["severity"] == "CRITICAL"  # fits her, reported 3.3x
    assert klarna["recommended_action"][0].startswith("Hold for person")
    assert klarna["top_signal"]["reported_x"] == 3.3
    synchrony = gate.check("Synchrony", "credit_card", ["irregular_income"])
    assert synchrony["severity"] == "HIGH"  # fits, but under 3x
    assert gate.check("Apple Card", "credit_card", [])["severity"] == "MODERATE"
    au = gate.check("AU Small Finance Bank", "credit_card", [])
    assert au["severity"] == "MODERATE" and au["india_rbi"]["x_vs_india"] == 3.0
    assert any("Key Facts Statement" in a for a in au["recommended_action"])
    assert gate.check("Nobody Bank", "credit_card", [])["severity"] == "LOW"
    assert gate.check("Klarna", "bnpl", ["irregular_income", "other_bnpl"]) == klarna  # deterministic
