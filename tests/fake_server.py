"""Run the app locally with the Gemini stand-in, for UI work without credentials.

    python -m tests.fake_server   ->  http://localhost:8080
"""
import uvicorn

from app import gemini
from tests import fakes

gemini.generate_json = fakes.fake

if __name__ == "__main__":
    uvicorn.run("app.main:app", port=8080)
