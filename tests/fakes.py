"""A stand-in for Gemini that returns fixed, schema-valid answers (tests and UI screenshots only)."""
import json

from app.schemas import (ClauseFindings, ClauseLink, ContractOnlyRisk, Contraindication, Interaction, LeafletText,
                         LineText, ProductCard, ProductType, StatedTerm)

REAL_QUOTE = "While we review a dispute you must continue to pay your scheduled instalments."
FAKE_QUOTE = "We will refund every disputed purchase within one day."


def fake(prompt, schema, **kw):
    text = prompt if isinstance(prompt, str) else " ".join(p for p in prompt if isinstance(p, str))
    if schema is ProductCard and "India" in text:
        return ProductCard(issuer_name="AU Small Finance Bank", brand_name="LIT Credit Card", product_type=ProductType.credit_card,
                           product_name="AU LIT Credit Card", jurisdiction="IN", headline_claims=["Lifetime free"],
                           stated_terms=[], left_unsaid=["Late payment charges"])
    if schema is ProductCard:
        return ProductCard(issuer_name="Example Lending Co.", brand_name="FlexiPay", product_type=ProductType.bnpl,
                           product_name="FlexiPay Pay-in-4", jurisdiction="US", headline_claims=["No hidden fees"],
                           stated_terms=[StatedTerm(name="APR", value="0%")], left_unsaid=["Late fee amount"])
    if schema is ClauseFindings:
        ids = [line.split("line_id=")[1].split(" |")[0] for line in text.splitlines() if "line_id=" in line]
        return ClauseFindings(
            links=[ClauseLink(line_id=ids[0], clause_found=True, quote="If a payment attempt fails, we may retry the payment method up to three times",
                              page=99, section="3.2", how_it_causes="Retries can trigger bank fees."),
                   ClauseLink(line_id=ids[-1], clause_found=True, quote=FAKE_QUOTE, page=4, section="6", how_it_causes="x")] if ids else [],
            contract_only=[ContractOnlyRisk(fae_code="I1", label="Store fails, you still pay", quote=REAL_QUOTE, page=4,
                                            section="6.2", how_it_causes="Payments continue during disputes.")])
    if schema is LeafletText:
        ids = [d["line_id"] for d in json.loads(text.split("SIDE EFFECTS\n")[1].split("\n\nREADER")[0])]
        return LeafletText(what_it_is="A way to split a purchase into payments.",
                           lines=[LineText(line_id=i, plain_explanation="Explained.", how_to_reduce_risk="Act.") for i in ids],
                           contraindications=[Contraindication(condition="Not suitable if your income is irregular", reason="r", based_on=ids[:1]),
                                              Contraindication(condition="Invented", reason="r", based_on=["made-up-id"])],
                           interactions=[], for_you="Watch the payment dates.")
    raise AssertionError(schema)
