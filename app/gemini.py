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

FAST_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
# The clause reader needs long context and careful reading.
DEEP_MODEL = os.environ.get("GEMINI_DEEP_MODEL", FAST_MODEL)


class LLMUnavailable(RuntimeError):
    pass


@lru_cache
def client():
    from google import genai

    vertex = os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("1", "true")
    if not vertex and not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
        raise LLMUnavailable("Set GEMINI_API_KEY, or GOOGLE_GENAI_USE_VERTEXAI=true with GOOGLE_CLOUD_PROJECT.")
    return genai.Client()


def generate_json(prompt: list | str, schema: type[BaseModel], *, model: str | None = None,
                  system: str | None = None, temperature: float = 0.2) -> BaseModel:
    """Call Gemini with a response schema and return the parsed object."""
    from google.genai import types

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
    if resp.parsed is None:
        return schema.model_validate_json(resp.text)
    return resp.parsed


def part_from_bytes(data: bytes, mime: str):
    from google.genai import types

    return types.Part.from_bytes(data=data, mime_type=mime)
