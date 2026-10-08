# APAC evidence

US CFPB complaints are the statistical engine because they are the only large, public,
firm-named complaint stories. Asia-Pacific sources are used to check that the same side
effects show up locally:

| Market | Source | Status |
|---|---|---|
| India | Consumer-court orders via the Indian Kanoon API (AI use permitted) | `indian_kanoon.py` written, needs an API token, not yet run |
| Australia | AFCA published determinations (~4,300 a year, firms named) | to do: download determinations, then code them with `pipeline/classify.py` |
| Singapore | MAS / FIDReC publish only ~40 anonymised case studies | no usable data; leaflets for Singapore products are clause-only and say so |

Insurance is out of scope: no market publishes usable complaint-level data for it.
Scraping app-store reviews is avoided because it breaks Google Play's terms.
