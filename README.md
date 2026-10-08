# SIDE EFFECTS

**Pharmacovigilance for money.** Every packet of paracetamol tells you what can go wrong. A credit card or a Buy Now Pay Later plan only tells you the interest rate. SIDE EFFECTS writes the missing leaflet.

Point your phone at an offer. SIDE EFFECTS runs the statistics drug regulators use on adverse-event reports over real consumer complaints, uses Gemini to find the exact contract clause behind each problem, and prints a medicine-style leaflet for you: possible side effects, who should not take it, interactions, and lenders with fewer reported problems. A pharmacist you can talk to answers questions about it. AI agents that apply for credit on someone's behalf can read the same leaflet as JSON before they sign their human up.

Theme: **01 BFSI: Intelligent Risk, Fraud & Financial Experiences** (Google Cloud AI Builder Cup 2026, team CyberNex - Vision Matters).

## What the leaflet says, and how we know

> **Purchase disputes left unresolved**: reported **2.1x** more often than at similar card issuers (817 complaints, 2024; still 2.1x in Jun-Sep 2026). *Bank-level complaint signal.*

That line is about Goldman Sachs (Apple Card). The US regulator fined Goldman $45M for exactly this in October 2024. The method would have flagged it from public complaints alone.

Every number comes from code, never from the model:

- **Statistic**: proportional reporting ratio (PRR) with a 95% interval, signal under the Evans rule (at least 3 reports, PRR at least 2, chi-square at least 4), the standard in drug-safety databases.
- **Honest wording**: complaints have no denominator, so the leaflet says "reported N times more often than similar lenders", never "common" or "rare", and states that reports are unverified.
- **Honest level**: each line says whether it is a *bank-level complaint signal* (how the company behaves), a *product-category signal* (for example all BNPL lenders), or a *clause in this contract*. Many harms have no clause behind them, and the leaflet says so.
- **Verified quotes**: Gemini proposes the clause; code checks the quote word for word against the contract and discards anything it cannot find.

## How it works

```
 photo / PDF / text
        │
 1. Intake agent ─────── Gemini (multimodal): what product, which lender, what the advert leaves unsaid
 2. Matcher ──────────── brand -> lender in the complaint database
 3. Signal engine ────── PRR vs peer lenders on 136k CFPB complaints (deterministic)
 4. Mechanism agent ──── Gemini (long context) reads the whole contract, pins each side effect to a clause
        │                  └─ every quote verified in code; unverifiable quotes are dropped
 5. Leaflet writer ───── Gemini writes contraindications and interactions for *your* situation,
        │                  only around line ids it was given (no numbers)
 6. Pharmacist agent ─── Gemini with tools: get_side_effects, search_contract, complaint_examples, compare_with
        │
 /api/v1/check ───────── deterministic gate for AI agents: no_signal / disclose / human_review
```

Offline, the **harvest pipeline** turns raw complaints into the signal table:

- `pipeline/classify.py` and `pipeline/bigquery/classify.sql`: Gemini codes each complaint story into a 26-term financial side-effect vocabulary and flags copy-paste credit-repair templates (19% of a hand-checked sample), which otherwise create false signals.
- `pipeline/bigquery/prr.sql`: the PRR statistics in BigQuery.
- `pipeline/eval_classifier.py`: precision, recall and F1 against 143 hand-labelled complaints, with a keyword baseline.
- `pipeline/build_data.py`: builds `app/data/` from the outputs.
- `pipeline/apac/`: India (Indian Kanoon consumer-court orders) and Australia (AFCA) validation.

## Data

| Source | Rows | Used for |
|---|---|---|
| US CFPB credit-card complaints, 2024 (credit bureaus removed from peers) | 75,989 | card issuer signals |
| US CFPB credit-card complaints, Jun-Sep 2026 | 21,293 | "still reported in 2026" / "new in 2026" |
| US CFPB personal loan / BNPL complaints | 38,988 | BNPL lender and category signals |
| Hand-labelled CFPB complaint stories | 143 | real stories on the leaflet, classifier evaluation |

Singapore regulators publish no complaint-level data, so Singapore products get a clause-only leaflet that says so. Insurance is out of scope for the same reason.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export GEMINI_API_KEY=...            # or GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION
uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080 and press **Try a sample**. The sample is a fictional BNPL agreement; for a real demo, upload a real card agreement PDF (US issuers publish theirs in the CFPB credit card agreement database).

Tests use a stand-in for Gemini, so they run without credentials: `pytest`. To click through the UI without credentials: `python -m tests.fake_server`.

Model: `GEMINI_MODEL` (default `gemini-2.5-flash`), and optionally `GEMINI_DEEP_MODEL` for the contract reader.

## Deploy to Cloud Run

```bash
PROJECT_ID=your-project ./deploy.sh
```

This enables the APIs, creates a service account with the Vertex AI User role, and deploys from source to Cloud Run in `asia-southeast1`. Gemini is called through Vertex AI with the service's own identity, so no API key is stored.

## For AI agents

`GET /.well-known/side-effects.json` describes the service. Before committing a person to a credit product an agent calls:

```http
POST /api/v1/check
{"issuer": "Apple Card", "product_type": "credit_card", "applicant_profile": ["big_purchase"]}
```

and gets `human_review` with the disclosure "Purchase disputes left unresolved: reported 2.1x more often than at peer lenders (817 complaints, Jan-Dec 2024; bank-level complaint signal; unverified reports)". The answer is deterministic, so the same request always gets the same answer.

## Limits

- Complaint data is issuer-level, not per card.
- Complaints are unverified and self-selected; signals show disproportion, not cause or probability.
- The hand-labelled set has a single annotator.
- Not financial advice.
