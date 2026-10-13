"""Run the app locally with the Gemini stand-in, for UI work without credentials.

    python -m tests.fake_server   ->  http://localhost:8080
"""
import time

import uvicorn

from app import gemini
from app.agents import shopper
from tests import fakes

gemini.generate_json = fakes.fake


def _slow_turn(*a, **kw):
    time.sleep(0.8)  # roughly a real model step, so the screen streams like the live demo
    return fakes.fake_shopper_turn(*a, **kw)


shopper._model_turn = _slow_turn

if __name__ == "__main__":
    uvicorn.run("app.main:app", port=8080)
