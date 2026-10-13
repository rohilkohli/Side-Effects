@echo off
REM Run SIDE EFFECTS on Windows. Needs Python 3.11+ (python.org) and a Gemini API key (aistudio.google.com/apikey).
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
if "%GEMINI_API_KEY%"=="" set /p GEMINI_API_KEY=Paste your Gemini API key and press Enter: 
echo Opening http://localhost:8080 ... press Ctrl+C here to stop.
start "" http://localhost:8080
python -m uvicorn app.main:app --port 8080
