"""Structured outputs the Gemini agents must return."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ProductType(str, Enum):
    credit_card = "credit_card"
    bnpl = "bnpl"
    personal_loan = "personal_loan"
    other = "other"


class StatedTerm(BaseModel):
    name: str = Field(description="e.g. 'APR', 'Late fee', 'Promotional period'")
    value: str = Field(description="exactly as printed")


class ProductCard(BaseModel):
    """What the Intake agent reads off a flyer, web page or contract."""
    issuer_name: str = Field(description="The lender or bank legally providing the credit, if shown; else the brand. Empty if unknown.")
    brand_name: str = Field(description="Consumer-facing brand or card name, e.g. 'Apple Card', 'Pay in 4'.")
    product_type: ProductType
    product_name: str
    jurisdiction: str = Field(description="Country whose law/regulator applies: US, AU, IN, SG, other or unknown.")
    headline_claims: list[str] = Field(description="The selling promises, verbatim and short, e.g. '0% interest'.")
    stated_terms: list[StatedTerm]
    left_unsaid: list[str] = Field(description="Important cost or risk facts a consumer would need that the material does NOT state (max 4).")


class Page(BaseModel):
    page: int
    text: str


class Transcript(BaseModel):
    pages: list[Page]


class ClauseLink(BaseModel):
    line_id: str
    clause_found: bool
    quote: str = Field(description="Verbatim sentence(s) copied exactly from the contract, max 60 words. Empty if not found.")
    page: int = Field(description="Page number from the === PAGE n === marker, 0 if not found.")
    section: str = Field(description="Section heading or number the quote sits under, if any.")
    how_it_causes: str = Field(description="One sentence: how this clause lets the side effect happen. Empty if not found.")


class ContractOnlyRisk(BaseModel):
    fae_code: str = Field(description="Code from the side-effect vocabulary, e.g. A1")
    label: str = Field(description="Short consumer-facing name of the side effect")
    quote: str = Field(description="Verbatim sentence(s) copied exactly from the contract, max 60 words.")
    page: int
    section: str
    how_it_causes: str


class ClauseFindings(BaseModel):
    links: list[ClauseLink]
    contract_only: list[ContractOnlyRisk] = Field(description="Up to 4 clauses that enable a vocabulary side effect not already in the list.")


class LineText(BaseModel):
    line_id: str
    plain_explanation: str = Field(description="What this side effect looks like in daily life, one or two sentences, no statistics.")
    how_to_reduce_risk: str = Field(description="One concrete action the consumer can take.")


class Contraindication(BaseModel):
    condition: str = Field(description="Starts with 'Not suitable if' or 'Take extra care if'.")
    reason: str
    based_on: list[str] = Field(description="line_ids this follows from")


class Interaction(BaseModel):
    with_what: str = Field(description="Another product, habit or situation, e.g. 'other Buy Now Pay Later plans'")
    effect: str
    based_on: list[str]


class LeafletText(BaseModel):
    what_it_is: str = Field(description="One sentence describing the product in plain words.")
    lines: list[LineText]
    contraindications: list[Contraindication]
    interactions: list[Interaction]
    for_you: str = Field(description="Two or three sentences for this person's situation. Never say 'safe' or give a guarantee.")


class Situation(str, Enum):
    irregular_income = "irregular_income"
    carries_balance = "carries_balance"
    other_bnpl = "other_bnpl"
    new_to_credit = "new_to_credit"
    big_purchase = "big_purchase"
    travels = "travels"


class ReadPerson(BaseModel):
    """What the shopping agent's intake step reads from a person describing themselves."""
    name: str = Field(description="Their first name if they gave one, else 'You'.")
    about: str = Field(description="One short third-person sentence restating their financial situation. No advice.")
    situations: list[Situation] = Field(description="Only situations the text clearly supports. irregular_income: gig, freelance, commission, seasonal, part-time or student income. carries_balance: may not pay a card in full. other_bnpl: already paying instalment, EMI or pay-later plans. new_to_credit: thin or damaged credit history. big_purchase: one large purchase. travels: spends abroad often.")
