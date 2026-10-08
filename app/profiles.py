"""Who a side effect hurts most.

Deterministic mapping from a person's situation to the side-effect codes
(data/vocabulary.json) that matter most for them. Used for contraindications
in the agent-check API, and given to the Composer agent as a hint.
"""

PROFILES = {
    "irregular_income": {
        "label": "My income is irregular (gig, freelance, commission)",
        "codes": {"A4", "B1", "B3", "G1", "G2", "A3"},
    },
    "carries_balance": {
        "label": "I may not pay the full balance every month",
        "codes": {"A1", "A2", "A3", "G2"},
    },
    "other_bnpl": {
        "label": "I already use other Buy Now Pay Later plans",
        "codes": {"B1", "B3", "A4", "G2", "E1"},
    },
    "new_to_credit": {
        "label": "I'm new to credit or rebuilding my score",
        "codes": {"E1", "E2", "C2", "A4"},
    },
    "big_purchase": {
        "label": "It's for one big purchase (furniture, medical, travel)",
        "codes": {"A1", "D2", "I1", "B2"},
    },
    "travels": {
        "label": "I travel or shop abroad often",
        "codes": {"C1", "C4", "D1", "A2"},
    },
}


def sensitive_codes(profile_keys: list[str]) -> set[str]:
    codes: set[str] = set()
    for k in profile_keys:
        codes |= PROFILES.get(k, {}).get("codes", set())
    return codes


def describe(profile_keys: list[str], note: str = "") -> str:
    parts = [PROFILES[k]["label"] for k in profile_keys if k in PROFILES]
    if note:
        parts.append(note)
    return "; ".join(parts) or "No personal details given."
