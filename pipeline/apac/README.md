# APAC evidence

US CFPB complaints are the statistical engine because they are the only large, public,
firm-named complaint stories. Asia-Pacific sources are used to check that the same side
effects show up locally:

| Market | Source | Status |
|---|---|---|
| India | RBI Ombudsman 2024-25: credit-card complaints per 1,000 cards by bank group (a true rate) | **loaded** (`build_india.py` -> `app/data/apac.json`), shown on Indian card leaflets |
| India | Banks' own published "top five grounds of complaints" (firm-named, mandated by RBI) | 6 banks read by hand (SBI, Canara, Bandhan, IndusInd, AU, Amex); not yet loaded |
| India | Consumer-court orders via the Indian Kanoon API (AI use permitted) | `indian_kanoon.py` written, needs an API token, not yet run |
| Australia | AFCA Datacube (complaints per named firm and product, six-monthly) and published determinations | not reachable from the build environment; Datacube is an interactive dashboard with no download |
| Singapore | MAS / FIDReC publish only ~40 anonymised case studies | no usable data; leaflets for Singapore products are clause-only and say so |

Insurance is out of scope: no market publishes usable complaint-level data for it.
Scraping app-store reviews is avoided because it breaks Google Play's terms.
