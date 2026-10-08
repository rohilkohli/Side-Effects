"""Mechanism agent: pins each side effect to the contract clause that enables it.

Gemini reads the whole contract (long context) and proposes a verbatim quote
per side effect. Every quote is then checked against the contract text in
code; quotes that are not found word for word are discarded, so a leaflet
never shows a clause the contract does not contain.
"""
from __future__ import annotations

import re

from .. import evidence, gemini
from ..schemas import ClauseFindings, Page

SYSTEM = """You are a consumer-credit lawyer working for patients, not for the lender.
For each listed side effect, find the clause in this contract that makes it possible
(a fee, a power to change terms, a dispute process, a payment allocation rule, an
arbitration or closure right). Quote it exactly, character for character, from the
contract text. If no clause plausibly enables it, set clause_found=false: many side
effects come from how a company behaves, not from its contract, and saying so is correct.
Then list up to 4 further clauses that enable a side effect from the vocabulary that is
not already listed."""


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def locate(quote: str, pages: list[Page]) -> int | None:
    """Page number where the quote appears verbatim (whitespace-insensitive), else None."""
    q = _norm(quote).rstrip(".")
    if len(q) < 12:
        return None
    for p in pages:
        if q in _norm(p.text):
            return p.page
    return None


def format_contract(pages: list[Page]) -> str:
    return "\n".join(f"=== PAGE {p.page} ===\n{p.text}" for p in pages)


def pin_clauses(pages: list[Page], lines: list[dict]) -> dict:
    vocab = "\n".join(f"{v['code']} {v['preferred_term']}: {v['definition']}" for v in evidence.vocabulary())
    listed = "\n".join(f"- line_id={l['id']} | {l['label']} (CFPB category: {l['cfpb_term']})" for l in lines) or "(none)"
    prompt = (f"SIDE-EFFECT VOCABULARY\n{vocab}\n\nSIDE EFFECTS TO EXPLAIN\n{listed}\n\n"
              f"CONTRACT\n{format_contract(pages)}")
    found: ClauseFindings = gemini.generate_json(prompt, ClauseFindings, model=gemini.DEEP_MODEL, system=SYSTEM, temperature=0)

    known = {l["id"] for l in lines}
    links, rejected = {}, 0
    for link in found.links:
        if link.line_id not in known or not link.clause_found:
            continue
        page = locate(link.quote, pages)
        if page is None:
            rejected += 1
            continue
        links[link.line_id] = {"quote": link.quote.strip(), "page": page, "section": link.section,
                               "how_it_causes": link.how_it_causes}
    extra = []
    codes = {v["code"]: v["preferred_term"] for v in evidence.vocabulary()}
    for risk in found.contract_only[:4]:
        page = locate(risk.quote, pages)
        if page is None or risk.fae_code not in codes:
            rejected += 1
            continue
        extra.append({"fae": risk.fae_code, "label": risk.label, "quote": risk.quote.strip(), "page": page,
                      "section": risk.section, "how_it_causes": risk.how_it_causes})
    return {"links": links, "contract_only": extra, "rejected_quotes": rejected}
