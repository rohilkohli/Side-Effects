"""India evidence: RBI Ombudsman complaints per 1,000 credit cards, by bank group.

Source: Reserve Bank of India, Annual Report of the Ombudsman Scheme 2024-25
(published 1 Dec 2025), Appendix 1.5 "RE group-wise statement of complaints
received by the ORBIOs (April 2024 - March 2025)". Copied by hand; row totals
checked against the report's grand totals.

Unlike US complaint data, RBI publishes a denominator (complaints per 1,000
cards), so these are true rates. Cards in force implied by the two columns
add up to 110.1M, which matches India's ~110M credit cards in March 2025.

Usage: python pipeline/apac/build_india.py [out_dir]
"""
import json
import sys
from pathlib import Path

SOURCE = {
    "name": "RBI Annual Report of the Ombudsman Scheme 2024-25, Appendix 1.5",
    "url": "https://rbi.org.in/Scripts/PublicationsView.aspx?id=23441",
    "period": "Apr 2024-Mar 2025",
}

# group: (credit-card complaints to the RBI Ombudsman, complaints per 1,000 credit cards)
CREDIT_CARDS = {
    "public_sector": ("Public sector banks", 3021, 0.114),
    "private_sector": ("Private sector banks", 32696, 0.420),
    "small_finance": ("Small finance banks", 1279, 1.141),
    "foreign": ("Foreign banks", 4266, 0.923),
}
NBFC_CARD_COMPLAINTS = 9063  # RBI publishes no per-card rate for NBFC issuers

GROUPS = {
    "public_sector": ["State Bank of India", "SBI", "Bank of Baroda", "Punjab National Bank", "PNB", "Canara Bank",
                      "Union Bank of India", "Bank of India", "Indian Bank", "Central Bank of India",
                      "Indian Overseas Bank", "UCO Bank", "Bank of Maharashtra", "Punjab & Sind Bank"],
    "private_sector": ["HDFC Bank", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "Kotak", "IndusInd Bank",
                       "Yes Bank", "RBL Bank", "IDFC First Bank", "IDFC FIRST", "Federal Bank", "Bandhan Bank",
                       "IDBI Bank", "South Indian Bank", "Karur Vysya Bank", "City Union Bank", "DCB Bank",
                       "Karnataka Bank", "CSB Bank", "Tamilnad Mercantile Bank", "Jammu & Kashmir Bank"],
    "small_finance": ["AU Small Finance Bank", "AU Bank", "Ujjivan Small Finance Bank", "Equitas Small Finance Bank",
                      "Jana Small Finance Bank", "Utkarsh Small Finance Bank", "Suryoday Small Finance Bank",
                      "ESAF Small Finance Bank", "Unity Small Finance Bank", "Shivalik Small Finance Bank",
                      "Capital Small Finance Bank", "North East Small Finance Bank"],
    "foreign": ["American Express Banking Corp", "American Express", "Amex", "HSBC", "Standard Chartered",
                "DBS Bank India", "Citibank", "Deutsche Bank", "Barclays Bank"],
    "nbfc": ["SBI Card", "SBI Cards and Payment Services", "Bajaj Finance", "Bajaj Finserv"],
}


def build(out: Path):
    cards = {k: c / r * 1000 for k, (_, c, r) in CREDIT_CARDS.items()}
    avg = sum(c for _, c, _ in CREDIT_CARDS.values()) / sum(cards.values()) * 1000
    groups = {k: {"label": label, "complaints": c, "per_1000_cards": r, "cards_in_force": round(cards[k]),
                  "x_vs_india": round(r / avg, 1)} for k, (label, c, r) in CREDIT_CARDS.items()}
    data = {"IN": {"source": SOURCE, "india_per_1000_cards": round(avg, 3),
                   "cards_in_force": round(sum(cards.values())), "credit_card_groups": groups,
                   "nbfc_card_complaints": NBFC_CARD_COMPLAINTS, "members": GROUPS}}
    json.dump(data, open(out / "apac.json", "w"), indent=1)
    print(f"India: {sum(cards.values()) / 1e6:.1f}M cards, {avg:.3f} complaints per 1,000")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent.parent / "app" / "data"))
