"""The SIDE EFFECTS gate: a deterministic check an AI agent runs before committing a person to credit.

No language model is in this loop, so the same lender, product and situation
always get the same verdict.
"""
from __future__ import annotations

from . import alerts, evidence, profiles


def check(issuer: str, product_type: str = "credit_card", applicant_profile: list[str] | None = None) -> dict:
    company = evidence.resolve_company(issuer, product_type)
    sig = evidence.signals_for(company, product_type)
    sensitive = profiles.sensitive_codes(applicant_profile or [])
    disclosures, matches = [], []
    for l in sig["lines"]:
        level = "bank-level complaint signal" if l["scope"] == "bank" else "product-category complaint signal"
        text = (f"{l['label']}: reported {l['reported_x']}x more often than at peer lenders "
                f"({l['n']:,} complaints, {l['period']}; {level}; unverified reports).")
        disclosures.append({"side_effect": l["label"], "fae_code": l["fae"], "reported_x": l["reported_x"],
                            "ci95": l["ci95"], "n": l["n"], "level": l["scope"], "text": text})
        if l["fae"] in sensitive and l["label"] not in matches:
            matches.append(l["label"])
    # Active safety alerts (new spikes found in the live complaint feed) count like side effects:
    # always disclosed, and a reason to stop when they hit the person's situation.
    keys = set(applicant_profile or [])
    live_alerts = alerts.active(company) if company else []
    for a in live_alerts:
        disclosures.append({"side_effect": a["label"], "fae_code": a["fae"], "reported_x": a["ratio"], "n": a["recent_n"],
                            "level": "safety_alert", "alert_id": a["id"],
                            "text": f"Safety alert {a['date']}: {a['facts']} (live CFPB feed; unverified reports)."})
        if keys & set(a["affects"]) and a["label"] not in matches:
            matches.append(a["label"])
    verdict = "human_review" if matches else ("disclose" if disclosures else "no_signal")
    india = _india_rate(issuer, product_type)
    severity, action = _severity(verdict, disclosures, matches, issuer, india)
    if not company and severity == "LOW":
        # No statistics is not the same as no problems: say so instead of calling it low risk.
        severity = "UNKNOWN"
        action = ["Not in the complaint records: check the lender's licence and read its key facts before signing"] + action[1:]
    top = max(disclosures, key=lambda d: d["reported_x"] or 0, default=None)
    return {
        "issuer_matched": company,
        "verdict": verdict,
        "severity": severity,
        "recommended_action": action,
        "top_signal": {k: top[k] for k in ("side_effect", "reported_x", "n", "level")} if top else None,
        "matches_applicant_situation": matches,
        "required_disclosures": disclosures,
        "india_rbi": india,
        "safety_alerts": [{"id": a["id"], "date": a["date"], "headline": a["headline"]} for a in live_alerts],
        "disclaimer": evidence.dataset_notes()["disclaimer"],
    }


def _india_rate(issuer: str, product_type: str) -> dict | None:
    """RBI Ombudsman complaints per card for the issuer's bank group (Indian credit cards only)."""
    group = evidence.india_group(issuer)
    g = evidence.apac().get("IN", {}).get("credit_card_groups", {}).get(group or "")
    if not g or product_type != "credit_card":
        return None
    return {"group": g["label"], "x_vs_india": g["x_vs_india"], "per_1000_cards": g["per_1000_cards"],
            "source": "RBI Ombudsman 2024-25"}


def _severity(verdict: str, disclosures: list[dict], matches: list[str], issuer: str,
              india: dict | None = None) -> tuple[str, list[str]]:
    """Fixed rules, so severity is as repeatable as the verdict:
    CRITICAL  a side effect that fits the person is reported 3x or more, or a live safety alert fits them
    HIGH      a side effect fits the person
    MODERATE  side effects to disclose, none specific to the person, or an Indian bank group with at
              least 2x the national complaint rate per card
    LOW       no complaint signal
    UNKNOWN   (set in check) the lender is not in the complaint records at all"""
    fitting = [d for d in disclosures if d["side_effect"] in matches]
    if fitting and any(d["level"] == "safety_alert" or (d["reported_x"] or 0) >= 3 for d in fitting):
        severity = "CRITICAL"
    else:
        severity = {"human_review": "HIGH", "disclose": "MODERATE"}.get(verdict, "LOW")
    action = {"human_review": ["Hold for person: they must see the matching side effects and confirm"],
              "disclose": ["Show the disclosures before signing"],
              "no_signal": ["Proceed: no complaint signal found (this is not a safety guarantee)"]}[verdict]
    if severity == "LOW" and india and india["x_vs_india"] >= 2:
        severity = "MODERATE"
        action = [f"Show the RBI complaint rate: {india['group'].lower()} draw {india['x_vs_india']}x the Indian average per card"]
    if evidence.india_group(issuer):
        action.append("Require Key Facts Statement review (RBI requires a KFS for retail loans and credit cards)")
    return severity, action
