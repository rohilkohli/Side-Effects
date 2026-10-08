"""Plain-language names for CFPB issue / sub-issue labels.

Each CFPB label maps to a consumer-facing "side effect" name and the closest
code in the financial adverse-event vocabulary (data/vocabulary.json).
Labels not listed fall back to the CFPB wording.
"""

PLAIN = {
    # --- issue level -----------------------------------------------------
    "Problem when making payments": ("Trouble making repayments go through", "B1"),
    "Fees or interest": ("Fees or interest you did not expect", "A2"),
    "Problem with additional add-on products or services": ("Unwanted add-ons or protection products", "F3"),
    "Problem with a company's investigation into an existing problem": ("Complaints not properly investigated", "H1"),
    "Struggling to pay your bill": ("Little help when you fall behind", "G1"),
    "Struggling to pay your loan": ("Little help when you fall behind", "G1"),
    "Advertising and marketing, including promotional offers": ("Promotional offer not honoured", "F2"),
    "Incorrect information on your report": ("Damage to your credit file", "E1"),
    "Was approved for a loan, but didn't receive money": ("Approved, but the money never arrived", "B2"),
    "Problem with a purchase shown on your statement": ("Disputed purchases not resolved", "D2"),
    "Problem with cash advance": ("Cash-advance problems", "A3"),
    "Credit monitoring or identity theft protection services": ("Paid-for protection services that disappoint", "F3"),
    "Vehicle was damaged or destroyed the vehicle": ("Collateral damaged during repossession", "G3"),
    "Vehicle was repossessed or sold the vehicle": ("Collateral repossessed or sold", "G3"),
    "Improper use of your report": ("Your credit report used without permission", "H2"),
    "Getting a credit card": ("Problems getting the card in the first place", "E2"),
    "Credit limit changed": ("Credit limit changed on you", "C2"),
    "Problem with fraud alerts or security freezes": ("Fraud alerts or freezes mishandled", "C4"),
    "Problems receiving the advance": ("Advance not received", "B2"),
    "Can't contact lender or servicer": ("Can't reach the lender", "H1"),
    "Unexpected fees": ("Fees you did not expect", "A2"),
    "Confusing or misleading advertising or marketing": ("Misleading advertising", "F2"),
    "Charged fees or interest you didn't expect": ("Fees or interest you did not expect", "A2"),
    "Can't stop withdrawals from your bank account": ("Can't stop repayments leaving your bank account", "B3"),
    "Money was taken from your bank account on the wrong day or for the wrong amount": ("Repayment taken on the wrong day or for the wrong amount", "B3"),
    "Loan payment wasn't credited to your account": ("Repayment not credited", "B1"),
    "Received a loan you didn't apply for": ("Loan opened in your name without consent", "D3"),
    "Closing your account": ("Trouble closing the account", "C5"),
    "Trouble using your card": ("Card stops working or limit problems", "C1"),
    # --- sub-issue level ------------------------------------------------
    "Fees or interest || Problem with fees": ("Fees you did not expect", "A2"),
    "Fees or interest || Unexpected increase in interest rate": ("Interest rate rises unexpectedly", "A3"),
    "Fees or interest || Charged too much interest": ("Charged more interest than expected", "A3"),
    "Closing your account || Can't close your account": ("Can't close the account", "C5"),
    "Closing your account || Company closed your account": ("Account closed by the bank", "C1"),
    "Advertising and marketing, including promotional offers || Didn't receive advertised or promotional terms": ("Promotional offer not honoured", "F2"),
    "Advertising and marketing, including promotional offers || Confusing or misleading advertising about the credit card": ("Misleading card advertising", "F2"),
    "Other features, terms, or problems || Problem with rewards from credit card": ("Rewards taken away or not paid", "F1"),
    "Other features, terms, or problems || Problem with balance transfer": ("Balance transfer goes wrong", "A1"),
    "Other features, terms, or problems || Add-on products and services": ("Unwanted add-ons or protection products", "F3"),
    "Other features, terms, or problems || Problem with cash advances": ("Cash-advance problems", "A3"),
    "Other features, terms, or problems || Problem with convenience check": ("Convenience-cheque problems", "A3"),
    "Other features, terms, or problems || Privacy issues": ("Your data shared or misused", "H2"),
    "Other features, terms, or problems || Problem with customer service": ("Customer-service runaround", "H1"),
    "Getting a credit card || Sent card you never applied for": ("Card sent that you never applied for", "D3"),
    "Getting a credit card || Card opened without my consent or knowledge": ("Card opened in your name without consent", "D3"),
    "Getting a credit card || Application denied": ("Application denied, often without a clear reason", "E2"),
    "Getting a credit card || Problem getting a working replacement card": ("Replacement card does not arrive or work", "C4"),
    "Getting a credit card || Delay in processing application": ("Application stuck in processing", "H1"),
    "Problem when making payments || You never received your bill or did not know a payment was due": ("Missed payments because no bill arrived", "A4"),
    "Problem when making payments || Problem during payment process": ("Payments not credited on time", "B1"),
    "Improper use of your report || Credit inquiries on your report that you don't recognize": ("Credit checks you did not authorise", "H2"),
    "Improper use of your report || Reporting company used your report improperly": ("Your credit report used without permission", "H2"),
    "Incorrect information on your report || Account status incorrect": ("Wrong account status on your credit file", "E1"),
    "Incorrect information on your report || Account information incorrect": ("Wrong account details on your credit file", "E1"),
    "Incorrect information on your report || Personal information incorrect": ("Wrong personal details on your credit file", "E1"),
    "Incorrect information on your report || Old information reappears or never goes away": ("Old debts reappear on your credit file", "E1"),
    "Incorrect information on your report || Information is missing that should be on the report": ("Good history missing from your credit file", "E1"),
    "Incorrect information on your report || Public record information inaccurate": ("Wrong public-record data on your credit file", "E1"),
    "Struggling to pay your bill || Credit card company won't work with you while you're going through financial hardship": ("No help during financial hardship", "G1"),
    "Problem with a purchase shown on your statement || Credit card company isn't resolving a dispute about a purchase on your statement": ("Purchase disputes left unresolved", "D2"),
    "Problem with a purchase shown on your statement || Card was charged for something you did not purchase with the card": ("Fraudulent charges left with you", "D1"),
    "Problem with a purchase shown on your statement || Overcharged for something you did purchase with the card": ("Overcharged on a real purchase", "D2"),
    "Problem with a company's investigation into an existing problem || Their investigation did not fix an error on your report": ("Credit-file errors not fixed after a dispute", "E1"),
    "Problem with a company's investigation into an existing problem || Problem with personal statement of dispute": ("Your dispute statement ignored", "E1"),
    "Problem with a company's investigation into an existing problem || Investigation took more than 30 days": ("Investigations take more than 30 days", "H1"),
    "Trouble using your card || Credit card company won't increase or decrease your credit limit": ("Credit limit won't be changed when you ask", "C2"),
    "Trouble using your card || Can't use card to make purchases": ("Card blocked from purchases", "C1"),
    "Problem with fraud alerts or security freezes || (no sub-issue)": ("Fraud alerts or freezes mishandled", "C4"),
    "Credit monitoring or identity theft protection services || Billing dispute for services": ("Billing disputes over protection services", "F3"),
    "Credit monitoring or identity theft protection services || Problem canceling credit monitoring or identify theft protection service": ("Can't cancel a protection service", "C5"),
    "Credit monitoring or identity theft protection services || Didn't receive services that were advertised": ("Protection service not delivered as advertised", "F2"),
}


def plain(term: str) -> tuple[str, str | None]:
    if term in PLAIN:
        return PLAIN[term]
    tail = term.split(" || ")[-1]
    return tail[:1].upper() + tail[1:], None
