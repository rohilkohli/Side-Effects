"""The SIDE EFFECTS pipeline: five steps, three of them Gemini agents.

  1. Intake (Gemini, multimodal)    flyer photo / page / contract -> product card
  2. Match  (code)                  brand -> CFPB company
  3. Signal (code, statistics)      proportional reporting ratios vs peers
  4. Mechanism (Gemini, long ctx)   side effect -> verbatim contract clause, checked in code
  5. Compose (Gemini)               personalised leaflet text around fixed numbers

`run` yields progress events so the UI can show each agent working.
"""
from __future__ import annotations

import io
import re
import uuid
from dataclasses import dataclass, field
from typing import Iterator

from . import evidence, gemini, profiles
from .agents import clauses, composer, intake
from .schemas import Page

US = {"US", "USA", "UNITED STATES"}
MAX_KEPT = 200
LEAFLETS: dict[str, dict] = {}
CONTRACTS: dict[str, list[dict]] = {}


@dataclass
class Inputs:
    images: list[tuple[bytes, str]] = field(default_factory=list)
    contract_pdf: bytes | None = None
    contract_text: str = ""
    flyer_text: str = ""
    issuer_override: str = ""
    product_type_override: str = ""
    profile: list[str] = field(default_factory=list)
    note: str = ""


def pages_from_text(text: str, chars: int = 3500) -> list[Page]:
    """Split pasted text into pages: on form feeds or '=== PAGE n ===' markers, else every ~3,500 characters."""
    marked = re.split(r"=== PAGE (\d+) ===", text)
    if len(marked) > 2:
        return [Page(page=int(marked[i]), text=marked[i + 1].strip()) for i in range(1, len(marked) - 1, 2)]
    chunks = text.split("\f") if "\f" in text else [text[i:i + chars] for i in range(0, len(text), chars)]
    return [Page(page=i + 1, text=c.strip()) for i, c in enumerate(chunks) if c.strip()]


def pages_from_pdf(data: bytes) -> list[Page]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [Page(page=i + 1, text=(p.extract_text() or "").strip()) for i, p in enumerate(reader.pages)]
    if sum(len(p.text) for p in pages) < 200 * max(1, len(pages)) // 2:
        return intake.transcribe(data)  # scanned PDF: let Gemini read it
    return pages


def run(inp: Inputs) -> Iterator[dict]:
    lid = uuid.uuid4().hex[:10]

    # 1. Contract text (if any) and Intake ------------------------------
    yield {"step": "read", "status": "running", "detail": "Reading what you gave us"}
    pages: list[Page] = []
    if inp.contract_pdf:
        pages = pages_from_pdf(inp.contract_pdf)
    elif inp.contract_text.strip():
        pages = pages_from_text(inp.contract_text)

    parts: list = [gemini.part_from_bytes(b, m) for b, m in inp.images]
    if inp.flyer_text.strip():
        parts.append("MARKETING MATERIAL:\n" + inp.flyer_text.strip())
    if pages:
        parts.append("CONTRACT (first pages):\n" + clauses.format_contract(pages[:4]))
    if not parts and inp.issuer_override.strip():
        # Only a name was typed: let Gemini describe the product from what it knows of the name.
        parts.append(f"The person typed only the name of the credit product or lender they are considering: "
                     f"{inp.issuer_override.strip()[:80]}. There is no advert, so leave headline_claims and left_unsaid empty. "
                     f"Give the bank that issues it as issuer_name when that is well known (Apple Card: Goldman Sachs).")
    if not parts:
        yield {"step": "read", "status": "error", "detail": "Add a photo or PDF of the offer, or type the card or lender's name."}
        return
    card = intake.read_product(parts)
    product = card.model_dump(mode="json")
    if inp.product_type_override:
        product["product_type"] = inp.product_type_override
    brand = card.brand_name or card.product_name
    lender = f", lent by {card.issuer_name}" if card.issuer_name and card.issuer_name != brand else ""
    yield {"step": "read", "status": "done", "detail": f"Found {brand}{lender} ({product['product_type'].replace('_', ' ')})",
           "product": product}

    # 2. Match to complaint data ----------------------------------------
    yield {"step": "match", "status": "running", "detail": "Finding this lender in the complaint database"}
    company = (evidence.resolve_company(inp.issuer_override) or evidence.resolve_company(card.issuer_name)
               or evidence.resolve_company(card.brand_name) or evidence.resolve_company(card.product_name))
    jurisdiction = (card.jurisdiction or "unknown").upper()
    product["matched_company"] = company
    yield {"step": "match", "status": "done",
           "detail": f"Matched to {company} in US CFPB complaints" if company else "No complaint record for this lender",
           "company": company}

    # 3. Pharmacovigilance statistics -----------------------------------
    yield {"step": "signal", "status": "running", "detail": "Comparing complaint rates with peer lenders"}
    sig = evidence.signals_for(company, product["product_type"])
    lines = sig["lines"]
    yield {"step": "signal", "status": "done",
           "detail": f"{len(lines)} side effect{'s' if len(lines) != 1 else ''} reported more often than at peers"
                     + (f" (from {sig['company_total']:,} complaints)" if sig["company_total"] else "")}

    # 4. Mechanism: pin to clauses --------------------------------------
    contract_only, rejected = [], 0
    if pages:
        yield {"step": "clauses", "status": "running", "detail": f"Reading all {len(pages)} pages of the contract for the clause behind each one"}
        found = clauses.pin_clauses(pages, lines)
        for l in lines:
            if l["id"] in found["links"]:
                l["clause"] = found["links"][l["id"]]
        contract_only, rejected = found["contract_only"], found["rejected_quotes"]
        yield {"step": "clauses", "status": "done",
               "detail": f"{len(found['links'])} linked to a clause, {len(contract_only)} more found only in the contract"
                         + (f", {rejected} unverifiable quote{'s' if rejected != 1 else ''} discarded" if rejected else "")}
    else:
        yield {"step": "clauses", "status": "skipped", "detail": "No contract given, so no clause links"}

    for l in lines:
        q = evidence.quotes_for(l["company"] if l["scope"] == "bank" else None, l["cfpb_term"], family=sig["family"])
        if not q and l["scope"] != "bank":
            q = evidence.quotes_for_code(l["fae"], family=sig["family"])
        l["stories"] = [{"text": x["text"], "date": x["date"], "complaint_id": x["complaint_id"]} for x in q]

    # 5. Compose ---------------------------------------------------------
    yield {"step": "compose", "status": "running", "detail": "Writing your leaflet"}
    all_lines = lines + [{"id": f"contract:{i}", "label": c["label"], "scope": "contract", "fae": c["fae"],
                          "cfpb_term": "", "clause": c} for i, c in enumerate(contract_only)]
    text = composer.compose(product, all_lines, inp.profile, inp.note)
    by_id = {t.line_id: t for t in text.lines}
    valid = {l["id"] for l in all_lines}
    for l in all_lines:
        t = by_id.get(l["id"])
        l["plain_explanation"] = t.plain_explanation if t else ""
        l["how_to_reduce_risk"] = t.how_to_reduce_risk if t else ""

    sensitive = profiles.sensitive_codes(inp.profile)
    leaflet = {
        "id": lid,
        "product": product,
        "what_it_is": text.what_it_is,
        "for_you": text.for_you,
        "profile": profiles.describe(inp.profile, inp.note),
        "side_effects": [dict(l, relevant_to_you=l.get("fae") in sensitive) for l in lines],
        "contract_only": [dict(c, id=f"contract:{i}", plain_explanation=by_id[f"contract:{i}"].plain_explanation if f"contract:{i}" in by_id else "",
                               how_to_reduce_risk=by_id[f"contract:{i}"].how_to_reduce_risk if f"contract:{i}" in by_id else "",
                               relevant_to_you=c["fae"] in sensitive)
                          for i, c in enumerate(contract_only)],
        "contraindications": [c.model_dump() for c in text.contraindications if set(c.based_on) <= valid],
        "interactions": [i.model_dump() for i in text.interactions if set(i.based_on) <= valid],
        "alternatives": evidence.alternatives(company, product["product_type"], [l["label"] for l in lines if l["scope"] == "bank"])
                        if company else [],
        "coverage": coverage_note(company, jurisdiction, bool(pages)),
        "local_evidence": evidence.local_evidence(jurisdiction, product["product_type"], inp.issuer_override,
                                                  card.issuer_name, card.brand_name, card.product_name),
        "evidence": evidence.dataset_notes(),
        "contract_pages": len(pages),
        "rejected_quotes": rejected,
    }
    LEAFLETS[lid] = leaflet
    CONTRACTS[lid] = [p.model_dump() for p in pages]
    while len(LEAFLETS) > MAX_KEPT:  # oldest first; dicts keep insertion order
        old = next(iter(LEAFLETS))
        LEAFLETS.pop(old); CONTRACTS.pop(old, None)
    yield {"step": "compose", "status": "done", "detail": "Leaflet ready"}
    yield {"step": "leaflet", "leaflet": leaflet}


def coverage_note(company: str | None, jurisdiction: str, has_contract: bool) -> str:
    if company and jurisdiction in US | {"UNKNOWN"}:
        return "Complaint statistics: US CFPB database, issuer level."
    if company:
        return (f"This product is sold in {jurisdiction}. Complaint statistics shown are for the same lender's US "
                "products (CFPB) and may not reflect local practice.")
    local = {"SG": "Singapore regulators publish no complaint-level data",
             "AU": "Australian ombudsman (AFCA) decisions are not yet loaded for this lender",
             "IN": "India has no complaint-level data; RBI Ombudsman rates by bank group are shown instead"}.get(jurisdiction, "No complaint data was found for this lender")
    return f"{local}. {'This leaflet is based on the contract only.' if has_contract else 'Add the contract to see clause-level side effects.'}"
