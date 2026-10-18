"""Voice agent: speech in, the same Gemini assistant and tools, a short spoken answer out.

The browser does speech-to-text when it can (Web Speech API) and sends text. Browsers without it record
audio with MediaRecorder and send the clip; Gemini on Vertex AI transcribes it here. The answer comes from
the site assistant (live complaint data, the gate, Google Search), told to keep it short enough to say
aloud, and is returned as display text plus a plain `speech` string the browser reads with speechSynthesis.
"""
from __future__ import annotations

import re
from typing import Iterator

from pydantic import BaseModel, Field

from . import gemini
from .agents import assistant

MAX_AUDIO_BYTES = 4 * 1024 * 1024  # about a minute of compressed speech
AUDIO_TYPES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "audio/aac")

SPOKEN = ("[Spoken question from the voice agent. Answer for listening: at most 3 short sentences, no lists, "
          "no markdown. For a question about a lender or an offer, call gate_check and say its risk severity "
          "first, then the top signal as 'reported N times more often than similar lenders', then the "
          "recommended action. Never say a number that no tool gave you.]\n")


class Heard(BaseModel):
    text: str = Field(description="Exactly what the speaker said, in their language; empty if no speech")


def transcribe(audio: bytes, mime: str) -> str:
    """Gemini listens to a short clip and writes down what was said."""
    heard = gemini.generate_json(
        [gemini.part_from_bytes(audio, mime),
         "Transcribe this question about credit, lenders or fees. Return only what was said."],
        Heard)
    return heard.text.strip()


def speakable(text: str) -> str:
    """Display text to something a speech engine reads cleanly: no markdown, links or symbols."""
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    t = re.sub(r"[*_`#>]+", "", t)
    t = re.sub(r"^\s*[-•]\s+", "", t, flags=re.M)
    t = re.sub(r"(\d)\s*[x×]\b", r"\1 times", t)
    return re.sub(r"\s+", " ", t).strip()


def run(text: str, history: list[dict], leaflet_id: str | None = None) -> Iterator[dict]:
    """Stream the assistant's tool calls, then a final event with the answer to show and to speak."""
    yield {"type": "heard", "text": text}
    answer = ""
    for ev in assistant.run(SPOKEN + text, history, leaflet_id):
        if ev["type"] == "say":
            answer = ev["text"]
        else:
            yield ev
    yield {"type": "final", "text": answer, "speech": speakable(answer), "speak": bool(answer)}
