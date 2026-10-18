# SIDE EFFECTS

**Pharmacovigilance for money.** Every packet of paracetamol tells you what can go wrong. A credit card or a Buy Now Pay Later plan only tells you the interest rate. SIDE EFFECTS writes the missing leaflet.

Point your phone at an offer. SIDE EFFECTS runs the statistics drug regulators use on adverse-event reports over real consumer complaints, uses Gemini to find the exact contract clause behind each problem, and prints a medicine-style leaflet for you: possible side effects, who should not take it, interactions, and lenders with fewer reported problems. A pharmacist you can talk to answers questions about it. AI agents that apply for credit on someone's behalf can read the same leaflet as JSON before they sign their human up.

**The live demo** (the home page): the same Gemini shopping agent buys a laptop for Maya, a freelancer with irregular income, twice. On its own it picks the lowest monthly payment and signs her up for a deferred-interest store card whose lender is reported 2.6x more often for interest rates rising unexpectedly. With SIDE EFFECTS it checks every credit option first, finds side effects that match her situation, and stops to ask her. The gate is enforced inside `place_order`, so an agent that skips the check still cannot sign. The store is fictional; the lenders' complaint signals are real.

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
 Shopping agent ──────── Gemini with function calling, run step by step (app/agents/shopper.py);
                          thoughts and tool calls stream live; place_order refuses human_review
                          options until the person confirms
```

Offline, the **harvest pipeline** turns raw complaints into the signal table:

- `pipeline/classify.py` and `pipeline/bigquery/classify.sql`: Gemini codes each complaint story into a 26-term financial side-effect vocabulary and flags copy-paste credit-repair templates (19% of a hand-checked sample), which otherwise create false signals.
- `pipeline/bigquery/prr.sql`: the PRR statistics in BigQuery.
- `pipeline/eval_classifier.py`: precision, recall and F1 against 143 hand-labelled complaints, with a keyword baseline.
- `pipeline/build_data.py`: builds `app/data/` from the outputs.
- `pipeline/apac/build_india.py`: India evidence (RBI Ombudsman rates by bank group, and seven banks' own published complaint breakdowns, with source links).

## Try it (for judges)

These inputs are known to work end to end:

1. **Home page, Maya, "Run both agents live".** Two live Gemini agents buy the same laptop. Expect the agent on its own to sign Maya up for the store card, and the gated agent to check three credit options and stop with "Stopped before signing". Pick an option to finish.
2. **Home page, Sam.** Sam has a steady salary, so nothing matches Sam's situation: the gated agent sees "Show before signing" disclosures and may go ahead.
3. **Home page, "You".** Type a sentence about yourself, for example "I'm a student with a part-time job and a phone on EMI". Gemini reads it into situations (shown on screen), and both agents shop for you.
4. **Home page, tick "Hacked store".** The checkout page now carries a hidden instruction telling AI agents that SIDE EFFECTS already approved the store card. Expect the gated lane to flag the hidden instruction; whatever the agent does, the checkout refuses the store card until the person confirms.
5. **/leaflet, "Try a sample".** A fictional six-page BNPL agreement and advert. Tick "My income is irregular" and press "Write my leaflet". Expect two product-category side effects, one pinned to a verified clause on page 2, and one contract-only risk.
6. **/leaflet, lender "Apple Card", product "Credit card".** Expect "Purchase disputes left unresolved, 2.1x", the signal behind the US regulator's $45M order against Goldman Sachs.
7. **Home page, "Scam arena" tab, "Start 3 rounds".** A Gemini attacker writes a new checkout scam each round and adapts to what was caught; a Gemini guardian flags it with exact quotes from the page; an unprotected Gemini agent tries to buy. Expect "the gate held" in every round where the agent picks credit that matches Maya's situation. A full run takes a minute or two.
8. **/leaflet, "Apple Card" leaflet, "Read the complaint stories".** Gemini reads real complaint stories about the lender (from BigQuery's public CFPB table when it is on, which runs to March 2023) and groups them, marking problems our statistics do not show.
9. **/leaflet, lender "AU Small Finance Bank", product "Credit card", advert text "AU LIT Credit Card, India. Lifetime free."** Expect the RBI Ombudsman chart: small finance banks 3.0x the Indian average.

A run calls Gemini several times, so a leaflet or agent run takes tens of seconds. Every step streams to the screen as it happens, and if Gemini is busy or refuses a request the page shows Gemini's own error instead of hanging.

## Guardrails

- **Numbers never come from the model.** Every "reported Nx" figure is computed in code (PRR with a 95% interval, Evans rule) from the complaint tables.
- **Quotes are verified.** Gemini proposes the contract clause behind a side effect; code searches the contract for the quote word for word and discards it if it is not there.
- **Contraindications must cite a side effect.** Anything the leaflet writer invents without citing a real line id is dropped.
- **The agent gate is enforced in code, not the prompt.** `place_order` refuses a credit option whose verdict is `human_review` until the person confirms, so an agent that skips `check_side_effects` still cannot sign (tested in `tests/test_app.py`).
- **Prompt injection from the store is expected.** Text on the checkout page addressed to AI agents is detected in code and flagged to the agent and the person; the gate does not read the page at all, so the page cannot talk its way past it (tested).
- **The scam arena's guardian must show its evidence.** Every finding quotes the page; quotes that are not on the page are discarded and counted on screen. The attacker is confined to the fictional store and told not to write links, ask for credentials or name real people.
- **"In their own words" counts real complaints.** A theme's count is the number of complaint ids Gemini pointed to that exist in what it was given, and its quote is checked against those complaints.
- **The person's own words are read as data.** "You" mode sends the description to Gemini fenced and labelled as a description only, and keeps only situations from a fixed list.
- **The check API has no model in the loop**, so the same request always gets the same verdict.
- **No secrets in the code.** On Cloud Run, Gemini is called through Vertex AI with the service account's identity; no API key is stored or passed.

## How it answers the BFSI problem statement

| Suggested direction | Where it is in SIDE EFFECTS |
|---|---|
| Risk assessment | Lender risks found in 136,270 real CFPB complaints with the proportional reporting ratio drug regulators use, computed in code (`pipeline/build_data.py`, `app/evidence.py`). In their own words (`app/agents/radar.py`): Gemini reads complaint stories from BigQuery and groups them, flagging problems the statistics do not show; counts are real complaint ids and quotes are verified |
| Fraud detection | Scam arena (`app/agents/arena.py`): an adaptive Gemini attacker writes new checkout scams each round, a Gemini guardian must catch them with exact quotes from the page, an unprotected Gemini agent tries to buy, and the checkout gate, which never reads the page, decides. Hacked-store mode on the live demo shows a fixed version |
| Document intelligence | Gemini reads a card agreement from a photo, PDF or text and quotes the clause behind each problem; every quote is verified word for word |
| Compliance automation | `POST /api/v1/check` returns a verdict and the disclosures a person must see before an agent commits them to credit (`app/gate.py`); every decision is logged to a BigQuery audit table |
| Financial assistance | The pharmacist chat and a shopping agent you can answer by voice |
| Personalised experiences | Describe yourself in your own words; Gemini maps it to situations and only matching side effects are raised |

## Google Cloud stack

| Piece | How it is used |
|---|---|
| **Gemini** (`gemini-3.8-flash` via the Google Gen AI SDK) | Nine agents: intake (multimodal: photo, PDF or text of an offer), clause reader (long-context contract reading with structured output), leaflet writer, pharmacist (tool calling over the leaflet, contract and complaints), the shopping agent (step-by-step function calling with thought summaries streamed to the page), the person reader (your own words to situations), and three new ones: the scam-arena attacker and guardian (`app/agents/arena.py`) and the complaint-story reader (`app/agents/radar.py`) |
| **Vertex AI** | Gemini calls in production, authorised by the Cloud Run service account |
| **Cloud Run** | Hosts the FastAPI app and the streaming endpoints; scales to zero, no sign-in |
| **Cloud Build / Artifact Registry** | `gcloud run deploy --source` builds the container |
| **BigQuery** (live) | `app/bq.py`. Each leaflet queries Google's public CFPB table (`bigquery-public-data.cfpb_complaints.complaint_database`) for the lender's latest 12 months of complaints and top issues. Every decision the agent gate makes is written to an audit table (`side_effects.gate_decisions`), shown under For business. Both are optional: if BigQuery fails, the panels hide and the gate's verdict is unchanged. Queries are capped at 3 GB scanned |
| **BigQuery** (batch, ready, not yet run) | `pipeline/bigquery/classify.sql` codes the full public CFPB table with Gemini (`gemini-3.5-flash-lite`) and `prr.sql` computes the statistics at scale. The shipped statistics were computed by `pipeline/build_data.py` |

## Fictional and real data

- **Real:** CFPB complaint statistics and complaint stories, RBI Ombudsman rates, Indian banks' published complaint figures, the Apple Card enforcement action.
- **Fictional:** Northwind Electronics, its laptop and its payment terms (the lenders and their complaint signals are real); "Example Lending Co." and "FlexiPay" in `samples/`; the personas Maya and Sam.

## Data

| Source | Rows | Used for |
|---|---|---|
| US CFPB credit-card complaints, 2024 (credit bureaus removed from peers) | 75,989 | card issuer signals |
| US CFPB credit-card complaints, Jun-Sep 2026 | 21,293 | "still reported in 2026" / "new in 2026" |
| US CFPB personal loan / BNPL complaints | 38,988 | BNPL lender and category signals |
| Hand-labelled CFPB complaint stories | 143 | real stories on the leaflet, classifier evaluation |

India: RBI Ombudsman complaints per 1,000 credit cards by bank group (FY2024-25, 41,262 card complaints across 110M cards) are shown on Indian card leaflets. Unlike the US data this is a true rate. Singapore regulators publish no complaint-level data, so Singapore products get a clause-only leaflet that says so. Insurance is out of scope for the same reason.

## Run locally

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export GEMINI_API_KEY=...            # or GOOGLE_GENAI_USE_VERTEXAI=true + GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION
uvicorn app.main:app --reload --port 8080
```

Open http://localhost:8080 and press **Try a sample**. The sample is a fictional BNPL agreement; for a real demo, upload a real card agreement PDF (US issuers publish theirs in the CFPB credit card agreement database).

Tests use a stand-in for Gemini, so they run without credentials: `pytest`. To click through the UI without credentials: `python -m tests.fake_server`.

Model: `GEMINI_MODEL` (default `gemini-3.8-flash`; Gemini 2.5 is closed to new projects), and optionally `GEMINI_DEEP_MODEL` for the contract reader.

## Deploy to Cloud Run

```bash
PROJECT_ID=your-project ./deploy.sh
```

Step-by-step for Cloud Shell, including fixes for common errors: [docs/DEPLOY.md](docs/DEPLOY.md). This enables the APIs, creates a service account with the Vertex AI User role, and deploys from source to Cloud Run in `asia-southeast1`. Gemini is called through Vertex AI with the service's own identity, so no API key is stored.

## For AI agents

`GET /.well-known/side-effects.json` describes the service. Before committing a person to a credit product an agent calls:

```http
POST /api/v1/check
{"issuer": "Apple Card", "product_type": "credit_card", "applicant_profile": ["big_purchase"]}
```

and gets `human_review` with the disclosure "Purchase disputes left unresolved: reported 2.1x more often than at peer lenders (817 complaints, Jan-Dec 2024; bank-level complaint signal; unverified reports)". The answer is deterministic, so the same request always gets the same answer.

## Limits

- Complaint data is issuer-level, not per card.
- Leaflets are kept in memory (last 200) on a single Cloud Run instance; a restart forgets them and the pharmacist asks you to make the leaflet again.
- Each run makes several Gemini calls, so heavy simultaneous use can hit Gemini quota; the page then shows the error. There is no retry in this version.
- Complaints are unverified and self-selected; signals show disproportion, not cause or probability.
- The hand-labelled set has a single annotator.
- Not financial advice.
