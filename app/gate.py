"""The SIDE EFFECTS gate: a deterministic check an AI agent runs before committing a person to credit.

No language model is in this loop, so the same lender, product and situation
always get the same verdict.
"""
from __future__ import annotations

from . import evidence, profiles


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
    verdict = "human_review" if matches else ("disclose" if disclosures else "no_signal")
    return {
        "issuer_matched": company,
        "verdict": verdict,
        "matches_applicant_situation": matches,
        "required_disclosures": disclosures,
        "disclaimer": evidence.dataset_notes()["disclaimer"],
    }
