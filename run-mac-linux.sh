#!/usr/bin/env bash
# Run SIDE EFFECTS locally. Needs Python 3.11+ and a Gemini API key (aistudio.google.com/apikey).
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
[ -n "$GEMINI_API_KEY" ] || read -rp "Paste your Gemini API key and press Enter: " GEMINI_API_KEY
export GEMINI_API_KEY
echo "Open http://localhost:8080  (Ctrl+C to stop)"
python -m uvicorn app.main:app --port 8080
