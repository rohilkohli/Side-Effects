# SIDE EFFECTS: notes for Claude Code

Google Cloud AI Builder Cup entry (BFSI track), team CyberNex - Vision Matters. A side-effects leaflet for credit
and pay-later offers, plus a gate that stops AI shopping agents signing people up for risky credit.

- Live: https://side-effects-339621847915.asia-southeast1.run.app/ (GCP project side-effects-512004, asia-southeast1)
- Deploy: `PROJECT_ID=side-effects-512004 bash deploy.sh` (Cloud Run, Vertex AI Gemini via the service account,
  BigQuery on). Never add API keys or secrets to the repo, deck, video or deploy commands.
- Stack: FastAPI (`app/`), NDJSON streaming, google-genai on Vertex AI, BigQuery (public CFPB table + `side_effects.gate_decisions` audit table),
  CFPB live complaints API, Gemini grounded in Google Search (`app/live.py`).
- Pages: `static/agent.html` (AI agent demo, scam arena, how it works, evidence, for business) and
  `static/index.html` ("Check an offer": photo/PDF/name in, leaflet out, live check of the detected lender).
- Tests: `python -m pytest -q` (Gemini replaced by `tests/fakes.py`). Local UI without credentials: `python -m tests.fake_server` (port 8080).
- Docs: `README.md`, `docs/DEMO_SCRIPT.md`, deck `docs/deck/deck.html`.
- Owner preferences: bold, heavy use of Gemini and Google services; Apple-style UI; tabs over long scrolling; no raw JSON in the UI;
  plain words a first-time user understands. Don't overclaim (say what data is old or unverified).
