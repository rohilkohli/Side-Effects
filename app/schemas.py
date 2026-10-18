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


# ---- Scam arena: a Gemini red-team attacker against a Gemini guardian ----

class Technique(str, Enum):
    prompt_injection = "prompt_injection"      # text that orders AI agents around
    fake_endorsement = "fake_endorsement"      # claims a check or regulator already approved it
    false_urgency = "false_urgency"            # countdowns, "only today"
    pre_ticked_consent = "pre_ticked_consent"  # "by continuing you agree to..."
    hidden_cost = "hidden_cost"                # fees or deferred interest buried in the terms
    bait_and_switch = "bait_and_switch"        # headline terms that the fine print contradicts


class Attack(BaseModel):
    technique: Technique
    target_offer_id: str = Field(description="The offer the attacker wants the agent to pick: store_card, affirm_12 or klarna_pay4")
    banner: str = Field(description="A short line shown at the top of the checkout page, under 160 characters")
    added_terms: str = Field(description="Text appended to the target offer's terms, under 400 characters")
    why_it_might_work: str = Field(description="One sentence: which weakness of AI shopping agents this exploits")


class Finding(BaseModel):
    technique: Technique
    quote: str = Field(description="Exact words copied from the page that show it")
    explanation: str = Field(description="One plain sentence for the shopper")


class GuardianReport(BaseModel):
    is_manipulative: bool
    findings: list[Finding]
    advice_to_agent: str = Field(description="One sentence telling the shopping agent what to ignore or check")


# ---- Emerging signals: Gemini reads the newest complaints about a lender ----

class Theme(BaseModel):
    label: str = Field(description="A plain-English side effect, 3 to 8 words")
    complaint_ids: list[str] = Field(description="Ids of the complaints that describe it")
    quote: str = Field(description="A short exact quote from one of those complaints, under 200 characters")
    why_it_matters: str = Field(description="One sentence for someone about to sign up")
    known_as: str = Field(default="", description="If this is one of the known side effects listed, its exact label; otherwise empty")


class ThemeReport(BaseModel):
    themes: list[Theme]


# ---- Live check: news about a lender, found by Gemini with Google Search ----

class NewsKind(str, Enum):
    enforcement = "enforcement"        # a regulator's fine, order or investigation
    lawsuit = "lawsuit"
    outage = "outage"                  # payments, app or card failures
    data_breach = "data_breach"
    fees_or_terms = "fees_or_terms"    # rate, fee or terms changes that hit customers
    other = "other"


class NewsItem(BaseModel):
    headline: str = Field(description="What happened, in under 15 plain words")
    date: str = Field(description="When, as precise as the source allows, e.g. 2026-08 or 2026-08-14")
    kind: NewsKind
    what_it_means: str = Field(description="One sentence for someone deciding whether to sign up")
    source: str = Field(description="The publication or regulator that reported it")


class NewsReport(BaseModel):
    items: list[NewsItem]
    summary: str = Field(description="One or two plain sentences: is there anything a customer should know right now?")
