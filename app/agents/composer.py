"""Composer agent: writes the leaflet's words around numbers it is not allowed to change."""
from __future__ import annotations

import json

from .. import gemini, profiles
from ..schemas import LeafletText

SYSTEM = """You write the patient information leaflet for a credit product, in the calm,
plain style of a medicine leaflet. Reading age 12. You are given side effects that were
found statistically in real complaint data or in the contract. Rules:
- Never invent or restate statistics, numbers or company facts: the leaflet prints those itself.
- Never call the product safe, unsafe, good or bad. Describe, don't judge.
- Contraindications and interactions must follow from the listed side effects (cite line_ids).
- A side effect with scope 'bank' is about how this company treats customers, not about the
  contract. Do not imply the contract causes it unless a clause is attached.
- Write one LineText for every line_id given."""


def compose(product: dict, lines: list[dict], profile_keys: list[str], note: str) -> LeafletText:
    slim = [{"line_id": l["id"], "side_effect": l["label"], "scope": l["scope"], "fae": l.get("fae"),
             "clause": (l.get("clause") or {}).get("quote")} for l in lines]
    sensitive = sorted(profiles.sensitive_codes(profile_keys))
    prompt = (f"PRODUCT\n{json.dumps(product)}\n\nSIDE EFFECTS\n{json.dumps(slim)}\n\n"
              f"READER'S SITUATION\n{profiles.describe(profile_keys, note)}\n"
              f"Side-effect codes that hit this situation hardest: {sensitive}")
    return gemini.generate_json(prompt, LeafletText, system=SYSTEM)
