"""Voice agent: speech in, the same Gemini assistant and tools, a short spoken answer out.

The browser does speech-to-text when it can (Web Speech API) and sends text. Browsers without it record
audio with MediaRecorder and send the clip; Gemini on Vertex AI transcribes it here. The answer comes from
the site assistant (live complaint data, the gate, Google Search), told to keep it short enough to say
aloud, and is returned as display text plus a plain `speech` string the browser reads with speechSynthesis.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Iterator

from pydantic import BaseModel, Field

from . import gemini, profiles
from .agents import assistant

log = logging.getLogger("side_effects.voice")
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


# ---------------------------------------------------------------------------
# One voice turn as structured JSON (POST /api/v1/voice/turn): what was heard, the answer to show and to say,
# every tool the agent called, the deterministic gate's verdict, follow-up questions and, on Cloud Run,
# the answer spoken by Google Cloud Text-to-Speech.
# ---------------------------------------------------------------------------

TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
TTS_VOICES = (os.environ.get("TTS_VOICE", "en-US-Chirp3-HD-Aoede"), "en-US-Neural2-F")
_tts_off = False


def _context_note(ctx: dict) -> str:
    """The page the person is on, the lender in front of them and their situation, as a note for the agent."""
    bits = []
    if ctx.get("active_lender"):
        bits.append(f"the lender in front of them is {str(ctx['active_lender'])[:80]}")
    keys = [k for k in ctx.get("applicant_profile") or [] if k in profiles.PROFILES]
    if keys:
        bits.append("their situation: " + ", ".join(keys) + " (pass these to gate_check as applicant_profile)")
    if ctx.get("current_page"):
        bits.append(f"they are on the {str(ctx['current_page'])[:40]} page")
    return f"[Context: {'; '.join(bits)}.]\n" if bits else ""


def _followups(lender: str | None, used: set[str]) -> list[str]:
    """Next questions to offer, chosen by fixed rules from what this turn covered (no model, no numbers)."""
    out = []
    if lender:
        if "gate_check" not in used:
            out.append(f"How risky is {lender} for someone with irregular income?")
        out.append(f"What should I ask {lender} before signing?")
        if "find_alternatives" not in used:
            out.append(f"Which lenders don't have {lender}'s problems?")
    if "india_rbi_data" in used:
        out.append("Which Indian bank group has the fewest complaints per card?")
    if "safety_alerts" not in used:
        out.append("Are there any new safety alerts this month?")
    out.append("How do Indian small finance banks compare in RBI data?" if "india_rbi_data" not in used
               else "Is Klarna safe for a freelancer with irregular income?")
    return list(dict.fromkeys(out))[:3]


def tts(text: str) -> str | None:
    """Speak the answer with Google Cloud Text-to-Speech (base64 MP3), only on Google Cloud; None otherwise,
    and the browser speaks it instead."""
    global _tts_off
    if _tts_off or not text or os.environ.get("TTS", "on").lower() == "off" or not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        return None
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        session = AuthorizedSession(creds)
        for name in TTS_VOICES:
            r = session.post(TTS_URL, timeout=10, json={
                "input": {"text": text[:4500]},
                "voice": {"languageCode": "en-US", "name": name},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.02}})
            if r.ok:
                return r.json().get("audioContent")
            if r.status_code in (401, 403):  # API off or no permission: stop trying until the next deploy
                _tts_off = True
                log.warning("Cloud Text-to-Speech unavailable (%s); the browser will speak instead", r.status_code)
                return None
    except Exception as e:
        log.warning("Cloud Text-to-Speech failed: %s", e)
    return None


def turn(text: str, history: list[dict], context: dict | None = None) -> dict:
    ctx = context if isinstance(context, dict) else {}
    tools_called: list[dict] = []
    verdicts: list[dict] = []
    links: list[dict] = []
    answer, lender = "", (str(ctx.get("active_lender") or "")[:80] or None)
    for ev in assistant.run(SPOKEN + _context_note(ctx) + text, history, ctx.get("leaflet_id")):
        if ev["type"] == "tool":
            tools_called.append({"name": ev["name"], "status": "running", "summary": ev["label"]})
            a = ev.get("args") or {}
            if ev["name"] != "open_page":
                lender = a.get("issuer") or a.get("name") or a.get("lender_a") or lender
        elif ev["type"] == "tool_done":
            t = next((t for t in tools_called if t["name"] == ev["name"] and t["status"] == "running"), None)
            if t:
                t["status"] = "ok" if ev.get("ok", True) else "error"
                t["summary"] = ev.get("summary") or t["summary"]
            if ev.get("verdict"):
                verdicts.append(ev)
        elif ev["type"] == "link":
            links.append({k: ev[k] for k in ("url", "page", "lender")})
        elif ev["type"] == "say":
            answer = ev["text"]
    # The strictest gate decision of the turn wins: one lender needing the person's word is enough to hold.
    verdict = None
    if verdicts:
        held = [v for v in verdicts if v["verdict"] == "human_review"]
        verdict = "human_review" if held else "pass"
    gate = (held or verdicts)[-1] if verdicts else None
    spoken = speakable(answer)
    return {
        "transcript": text,
        "reply_text": answer,
        "spoken_summary": spoken,
        "tools_called": tools_called,
        "gate_verdict": verdict,
        "gate_severity": gate.get("severity") if gate else None,
        "gate_issuer": gate.get("issuer") if gate else None,
        "suggested_followups": _followups(lender, {t["name"] for t in tools_called}),
        "links": links,
        "tts_audio_b64": tts(spoken),
    }
