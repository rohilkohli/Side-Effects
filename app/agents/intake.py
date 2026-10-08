"""Intake agent: reads a flyer photo, web page or contract and says what product it is."""
from __future__ import annotations

from .. import gemini
from ..schemas import Page, ProductCard, Transcript

SYSTEM = """You are the intake desk of SIDE EFFECTS, a service that writes a medicine-style
side-effects leaflet for consumer credit products. You read marketing material and contracts.
Identify the product exactly as presented. Copy promises and terms verbatim. In left_unsaid,
list facts a careful pharmacist would want on the label (what happens after a promo ends,
late-fee amounts, who the actual lender is) that the material does not state. Do not guess
values that are not shown."""


def read_product(parts: list) -> ProductCard:
    prompt = parts + ["Identify this financial product."]
    return gemini.generate_json(prompt, ProductCard, system=SYSTEM)


def transcribe(pdf_bytes: bytes) -> list[Page]:
    """For scanned contracts with no text layer: Gemini reads the pages."""
    t = gemini.generate_json(
        [gemini.part_from_bytes(pdf_bytes, "application/pdf"),
         "Transcribe every page of this contract verbatim. One entry per page, numbered from 1."],
        Transcript, model=gemini.DEEP_MODEL, temperature=0)
    return t.pages
