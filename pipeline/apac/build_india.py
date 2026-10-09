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


# Banks' own FY2024-25 complaint disclosures (RBI requires each bank to publish its top
# five grounds of complaints). Figures were read from each bank's PDF; spot-check
# against the PDF before quoting them publicly. Big private banks (HDFC, ICICI,
# Axis, Kotak) put this inside their annual reports, which we could not read here.
BANK_DISCLOSURES = {
    "State Bank of India": ("https://sbi.bank.in/documents/53471/263971/Statement+of+Complaints+Received+and+Disposed+during+the+FY+2024-25.pdf/90db37b0-246f-495f-576e-f5637eb17526",
                            2850520, [("Internet/mobile/electronic banking", 1757070), ("ATM/debit cards", 706788),
                                      ("Operation of accounts", 44631), ("Loans and advances", 15539),
                                      ("Excessive charges", 11694)]),
    "Canara Bank": ("https://canarabank.com/UploadedFiles/Pdf/Disclosure_of_Complaints_MARCH02025.pdf",
                    397084, [("Internet/mobile/electronic banking", 145076), ("ATM/debit cards", 76105),
                             ("Charges without notice / excessive charges", 14703), ("Loans and advances", 11798),
                             ("Account opening / operation", 9261)]),
    "Bandhan Bank": ("https://bandhan.bank.in/sites/default/files/2026-02/Complaint-Analysis-FY-2024-25.pdf",
                     155958, [("Internet/mobile/electronic banking", 46068), ("Account opening / operation", 41831),
                              ("ATM/debit cards", 26718), ("Loans and advances", 12016),
                              ("Cross-selling / para-banking", 5141)]),
    "AU Small Finance Bank": ("https://www.au.bank.in/notice-board-language/complaint-analysis-2024-25/English.pdf",
                              46801, [("Credit cards", 19749), ("ATM/debit cards", 9777),
                                       ("Account opening / operation", 2535), ("Staff behaviour", 423),
                                       ("Internet/mobile/electronic banking", 320)]),
    "American Express Banking Corp": ("https://www.americanexpress.com/content/dam/amex/in/legal/customer-complaint-grievance-redressal-policy/american-express-banking-corp-fy-2024-25.pdf",
                                      70971, [("Credit cards", 34469), ("Account opening / operation", 9471),
                                              ("Charges without notice / excessive charges", 7121),
                                              ("Fair Practices Code not followed", 3213),
                                              ("Mis-selling / para-banking", 2394)]),
    "Ujjivan Small Finance Bank": ("https://www.ujjivansfb.in/sites/default/files/2025-06/Analysis-and-Disclosure-of-Customer-Complaints-FY-2024-25.pdf",
                                   15553, [("ATM/debit cards", 6499), ("Internet/mobile/electronic banking", 2287),
                                           ("Account opening / operation", 1932), ("Loans and advances", 718)]),
    "DCB Bank": ("https://www.dcb.bank.in/api/dcb/assets/2025-07/Status-of-Complaints-fo-FY-2024-25.pdf",
                 24727, [("ATM/debit cards", 9738), ("Loans and advances", 8435),
                         ("Internet/mobile/electronic banking", 2986), ("Account opening / operation", 1441),
                         ("Para-banking", 555), ("Mis-selling", 275)]),
}
DISCLOSURE_ALIASES = {"SBI": "State Bank of India", "AU Bank": "AU Small Finance Bank", "Amex": "American Express Banking Corp",
                      "American Express": "American Express Banking Corp"}


def build(out: Path):
    cards = {k: c / r * 1000 for k, (_, c, r) in CREDIT_CARDS.items()}
    avg = sum(c for _, c, _ in CREDIT_CARDS.values()) / sum(cards.values()) * 1000
    groups = {k: {"label": label, "complaints": c, "per_1000_cards": r, "cards_in_force": round(cards[k]),
                  "x_vs_india": round(r / avg, 1)} for k, (label, c, r) in CREDIT_CARDS.items()}
    data = {"IN": {"source": SOURCE, "india_per_1000_cards": round(avg, 3),
                   "cards_in_force": round(sum(cards.values())), "credit_card_groups": groups,
                   "nbfc_card_complaints": NBFC_CARD_COMPLAINTS, "members": GROUPS,
                   "bank_disclosures": {bank: {"url": url, "total": total, "period": "Apr 2024-Mar 2025",
                                               "grounds": [{"ground": g, "complaints": n, "share": round(n / total, 3)}
                                                           for g, n in grounds]}
                                        for bank, (url, total, grounds) in BANK_DISCLOSURES.items()},
                   "disclosure_aliases": DISCLOSURE_ALIASES}}
    json.dump(data, open(out / "apac.json", "w"), indent=1)
    print(f"India: {sum(cards.values()) / 1e6:.1f}M cards, {avg:.3f} complaints per 1,000")


if __name__ == "__main__":
    build(Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent.parent.parent / "app" / "data"))
