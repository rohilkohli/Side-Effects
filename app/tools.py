"""The SIDE EFFECTS tool set, shared by the Gemini assistant on the site and by the MCP endpoint.

Every tool is a plain function with a docstring, so Gemini can call it (function calling) and other
AI agents can call it over MCP. Each returns JSON-ready data built from our statistics, the
regulator's live feed or Google Search; none of them lets a model make up a number.
"""
from __future__ import annotations

from . import alerts, evidence, gate, live, profiles

PRODUCT_TYPES = ("credit_card", "bnpl", "personal_loan")


def _ptype(product_type: str | None) -> str:
    return product_type if product_type in PRODUCT_TYPES else "credit_card"


def check_lender(name: str, product_type: str = "credit_card") -> dict:
    """Look up a lender or card by name (e.g. 'Apple Card', 'Klarna', 'Capital One'): which side effects are
    reported unusually often compared with similar lenders, and how many complaints the US regulator received
    about it in the last 90 days, with the trend and top issues. product_type is credit_card, bnpl or personal_loan."""
    d = live.check(name[:80], _ptype(product_type))
    c = d.get("complaints") or {}
    note = "reported_x means how many times more often than at similar lenders. Complaints are unverified."
    if not d["company"]:
        note = ("Not in our complaint statistics" + (f", but found in the regulator's live database as {d['live_company']}"
                if d.get("live_company") else "") + ". Call research_lender to find out who this lender is and whether it is licensed.")
    return {"name": d["name"], "company_in_records": d["company"], "company_in_live_feed": d.get("live_company"),
            "side_effects": d["signals"],
            "complaints_last_90_days": c.get("last_90_days"), "change_vs_previous_90_days_pct": c.get("change_pct"),
            "top_complaint_issues": c.get("top_issues", []), "newest_complaint": c.get("latest_complaint"), "note": note}


def research_lender(name: str, product_type: str = "credit_card") -> dict:
    """For a lender that is not in the complaint records (check_lender says so): Gemini searches the web for who
    actually lends, its licence and regulator, regulator actions, scam warnings and where complaints about it are
    published, with sources. Slower (about 10 seconds the first time)."""
    d = live.profile(name[:80], _ptype(product_type))
    if not d.get("available"):
        return {"available": False, "reason": d.get("reason")}
    keys = ("legal_name", "country", "what_it_offers", "regulated_by", "licence_found", "complaint_records",
            "red_flags", "what_to_check", "summary")
    return {**{k: d[k] for k in keys}, "sources": d["sources"][:6]}


def lender_news(name: str, product_type: str = "credit_card") -> dict:
    """Recent news about a lender found with Google Search: regulator fines, lawsuits, outages, data breaches and
    fee changes, with the sources. Slower than the other tools (about 10 seconds the first time)."""
    d = live.news(name[:80], _ptype(product_type))
    if not d.get("available"):
        return {"available": False, "reason": d.get("reason")}
    return {"summary": d["summary"], "items": d["items"], "sources": d["sources"][:6]}


def compare_lenders(lender_a: str, lender_b: str, product_type: str = "credit_card") -> dict:
    """Compare two lenders' side effects side by side, e.g. 'Apple Card' and 'Citi'."""
    pt = _ptype(product_type)
    a, b = evidence.resolve_company(lender_a, pt), evidence.resolve_company(lender_b, pt)
    if not a or not b:
        missing = [n for n, c in ((lender_a, a), (lender_b, b)) if not c]
        return {"error": f"No complaint records for: {', '.join(missing)}."}
    side = lambda c: [{"side_effect": l["label"], "reported_x": l["reported_x"]} for l in evidence.signals_for(c, pt)["lines"]]
    return {"a": {"name": lender_a, "company": a, "side_effects": side(a)},
            "b": {"name": lender_b, "company": b, "side_effects": side(b)}}


def find_alternatives(name: str, product_type: str = "credit_card") -> dict:
    """Similar lenders that do not share this lender's complaint signals (about complaint patterns only, not price)."""
    pt = _ptype(product_type)
    company = evidence.resolve_company(name, pt)
    labels = [l["label"] for l in evidence.signals_for(company, pt)["lines"]] if company else []
    return {"company": company, "its_side_effects": labels,
            "alternatives": [{"company": a["company"], "complaints": a["complaints"], "other_signals": a["total_signals"],
                              "clear_of": a["clear_of"]} for a in evidence.alternatives(company, pt, labels)]}


def gate_check(issuer: str, product_type: str = "credit_card", applicant_profile: list[str] | None = None) -> dict:
    """The deterministic SIDE EFFECTS gate an AI shopping agent must call before signing a person up for credit.
    applicant_profile keys: irregular_income, carries_balance, other_bnpl, new_to_credit, big_purchase, travels.
    Verdicts: no_signal, disclose (show the side effects first) or human_review (the person must confirm).
    Also returns severity (CRITICAL, HIGH, MODERATE, LOW), recommended_action and top_signal, all from fixed rules."""
    keys = [k for k in (applicant_profile or []) if k in profiles.PROFILES]
    return gate.check(issuer[:80], _ptype(product_type), keys)


def safety_alerts(name: str = "", product_type: str = "credit_card") -> dict:
    """Safety alerts from the last 30 days: problems suddenly reported much more often at a lender, found by scanning
    the regulator's live complaint feed. Pass a lender name for its alerts, or leave it empty for all of them."""
    found = alerts.for_name(name, _ptype(product_type)) if name else alerts.active()
    return {"alerts": [{k: a[k] for k in ("date", "company", "headline", "what_changed", "who_should_care", "what_to_do",
                                          "possible_cause", "ratio", "affects")} for a in found[:8]],
            "note": "Found by comparing the last 45 days of complaints with the 180 days before. Complaints are unverified."}


def india_rbi_data(bank: str = "") -> dict:
    """Indian credit-card complaint rates from the RBI Ombudsman annual report 2024-25: complaints per 1,000 cards for
    each bank group (public sector, private sector, small finance, foreign) against the national rate, and a bank's
    own published complaint breakdown when we have it. Pass an Indian bank name (e.g. 'AU Small Finance Bank',
    'HDFC Bank') or leave it empty for all groups."""
    india = evidence.apac().get("IN", {})
    if not india:
        return {"available": False, "reason": "No Indian data loaded."}
    group = evidence.india_group(bank) if bank else None
    out = {"source": india["source"], "india_per_1000_cards": india["india_per_1000_cards"],
           "cards_in_force": india["cards_in_force"],
           "groups": [{"group": k, **g} for k, g in india["credit_card_groups"].items()],
           "note": "x_vs_india is the group's complaints per card divided by the national rate. Complaints are unverified."}
    if bank:
        out["bank"], out["bank_group"] = bank, group
        if group == "nbfc":
            out["nbfc_card_complaints"] = india["nbfc_card_complaints"]
        disc = evidence.india_disclosure(bank)
        if disc:
            out["bank_disclosure"] = disc
    return out


def open_page(page: str, lender: str = "") -> dict:
    """Send the person to a page of the site. page is one of: leaflet (a full side-effects leaflet for a lender or
    offer; pass lender), agent_demo (two AI shopping agents, one protected), scam_arena (Gemini invents scams against
    AI shoppers), safety_alerts, evidence, business."""
    urls = {"leaflet": "/leaflet" + (f"?q={lender[:80]}" if lender else ""), "agent_demo": "/", "scam_arena": "/#scam",
            "safety_alerts": "/#alerts",
            "evidence": "/#why", "business": "/#biz"}
    return {"url": urls.get(page, "/"), "page": page}


ALL = [check_lender, research_lender, lender_news, safety_alerts, compare_lenders, find_alternatives, gate_check,
       india_rbi_data, open_page]
BY_NAME = {f.__name__: f for f in ALL}
# Tools the assistant may use; MCP clients get the same set minus navigation, which only makes sense on the site.
MCP_TOOLS = [f for f in ALL if f is not open_page]
