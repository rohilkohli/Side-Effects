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
    return {
        "issuer_matched": company,
        "verdict": verdict,
        "matches_applicant_situation": matches,
        "required_disclosures": disclosures,
        "safety_alerts": [{"id": a["id"], "date": a["date"], "headline": a["headline"]} for a in live_alerts],
        "disclaimer": evidence.dataset_notes()["disclaimer"],
    }
