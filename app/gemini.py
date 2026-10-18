"""One place that talks to Gemini.

Works with either a Gemini API key (GEMINI_API_KEY) or Vertex AI on Google
Cloud (GOOGLE_GENAI_USE_VERTEXAI=true, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION);
the google-genai SDK reads those variables itself. On Cloud Run the service
account supplies Vertex AI credentials, so no key is stored anywhere.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel

# Gemini 2.5 is closed to new projects; 3.x models are the current stable line.
FAST_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
# The clause reader needs long context and careful reading.
DEEP_MODEL = os.environ.get("GEMINI_DEEP_MODEL", FAST_MODEL)


class LLMUnavailable(RuntimeError):
    pass


class LLMEmpty(RuntimeError):
    """Gemini answered with nothing usable (for example a blocked or empty response)."""


RETRY_CODES = {429, 500, 502, 503, 504}


def with_retries(call, attempts: int = 3):
    """Run a Gemini call, retrying briefly when the service is busy or the answer is empty."""
    import time
    from google.genai import errors

    for i in range(attempts):
        try:
            return call()
        except errors.APIError as e:
            if e.code not in RETRY_CODES or i == attempts - 1:
                raise
        except LLMEmpty:
            if i == attempts - 1:
                raise
        time.sleep(1.5 * (i + 1))


@lru_cache
def client():
    from google import genai

    vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true")
    if not vertex and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise LLMUnavailable("Set GEMINI_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI=true with GOOGLE_CLOUD_PROJECT.")
    return genai.Client()


def generate_json(prompt: list | str, schema: type[BaseModel], *, model: str | None = None,
                  system: str | None = None, temperature: float | None = None) -> BaseModel:
    """Call Gemini with a response schema and return the parsed object.

    Temperature is left at the model default unless asked: Gemini 3 models are
    tuned for their default and can loop at low temperatures."""
    from google.genai import types

    def call():
        resp = client().models.generate_content(
            model=model or FAST_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        if resp.parsed is not None:
            return resp.parsed
        if not resp.text:
            raise LLMEmpty(f"Gemini returned no {schema.__name__}")
        return schema.model_validate_json(resp.text)

    return with_retries(call)


def part_from_bytes(data: bytes, mime: str):
    from google.genai import types

    return types.Part.from_bytes(data=data, mime_type=mime)
