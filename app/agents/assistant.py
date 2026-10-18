"""Site assistant: a Gemini agent that answers any question about credit side effects using live tools.

It runs the function-calling loop itself (automatic calling off) so every tool call can be streamed to
the page as it happens: the person sees which lender was looked up and where each number came from.
On a leaflet page it also gets the pharmacist's tools for that leaflet and its contract.
"""
from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from .. import gemini, pipeline, tools
from . import pharmacist

log = logging.getLogger("side_effects.assistant")
MAX_STEPS = 6

SYSTEM = """You are the SIDE EFFECTS assistant. SIDE EFFECTS writes medicine-style side-effects leaflets for
credit cards, loans and Buy Now Pay Later plans, from real complaint data, and gives AI shopping agents a
gate to call before they sign someone up for credit.

Answer any question a person has about credit, lenders, fees, complaints, scams or this site. Rules:
- Use your tools for every fact about a lender: complaint numbers, side effects, news. Never invent numbers.
  Call several tools at once when the question needs them (for example check_lender and lender_news together).
- Say "reported N times more often than at similar lenders", never a probability. Complaints are unverified.
- Give general explanations of credit terms (APR, deferred interest, minimum payment) from your own knowledge.
- You are not a financial adviser: never tell someone to sign or not; say what to watch for and what to ask.
- When a full leaflet, the agent demo or the scam arena would help, call open_page so the person gets a button.
- Keep answers short: 2 to 5 sentences, or a few bullet points. Plain words. If a leaflet is open, prefer its tools."""

TOOL_LABEL = {
    "check_lender": "Checking complaints for {name}",
    "lender_news": "Searching Google for news about {name}",
    "compare_lenders": "Comparing {lender_a} with {lender_b}",
    "find_alternatives": "Finding lenders without the same problems",
    "gate_check": "Running the SIDE EFFECTS gate for {issuer}",
    "open_page": "Preparing a link",
    "get_side_effects": "Reading this leaflet",
    "search_contract": "Searching the contract for \"{query}\"",
    "complaint_examples": "Reading real complaints about {side_effect}",
    "compare_with": "Comparing with {other_issuer}",
}
_pool = ThreadPoolExecutor(max_workers=6)


def _label(name: str, args: dict) -> str:
    try:
        return TOOL_LABEL.get(name, name).format(**{k: str(v)[:60] for k, v in args.items()})
    except KeyError:
        return TOOL_LABEL.get(name, name).split(" {")[0].split(" for")[0]


def _summary(name: str, out) -> str:
    """One short line about what a tool found, for the trace under the answer."""
    if not isinstance(out, dict):
        return ""
    if name == "check_lender":
        n = out.get("complaints_last_90_days")
        k = len(out.get("side_effects") or [])
        if not out.get("company_in_records"):
            return "Not in the US complaint records"
        return (f"{n:,} complaints in 90 days · " if n is not None else "") + f"{k} side effect{'s' if k != 1 else ''}"
    if name == "lender_news":
        if not out.get("summary"):
            return out.get("reason") or ""
        n, k = len(out.get("items") or []), len(out.get("sources") or [])
        return f"{n} news item{'s' if n != 1 else ''}, {k} source{'s' if k != 1 else ''}"
    if name == "gate_check":
        return "Verdict: " + str(out.get("verdict", "")).replace("_", " ")
    if name == "find_alternatives":
        return f"{len(out.get('alternatives') or [])} alternatives"
    return ""


def _turn(contents: list, toolset: list):
    from google.genai import types

    def call():
        resp = gemini.client().models.generate_content(
            model=gemini.FAST_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM,
                tools=toolset,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            ),
        )
        content = resp.candidates[0].content if resp.candidates else None
        if content is None or not content.parts:
            return types.Content(role="model", parts=[types.Part.from_text(text="")])
        return content

    return gemini.with_retries(call)


def run(question: str, history: list[dict], leaflet_id: str | None = None) -> Iterator[dict]:
    from google.genai import types

    toolset = list(tools.ALL)
    leaflet = pipeline.LEAFLETS.get(leaflet_id) if leaflet_id else None
    preface = ""
    if leaflet:
        toolset += pharmacist.build_tools(leaflet, pipeline.CONTRACTS.get(leaflet_id, []))
        p = leaflet["product"]
        preface = (f"[The person has the leaflet for {p.get('brand_name') or p.get('product_name')} "
                   f"({p.get('product_type')}, lender in records: {p.get('matched_company') or 'none'}) open.]\n")
    by_name = {f.__name__: f for f in toolset}

    contents = [types.Content(role=h["role"], parts=[types.Part.from_text(text=h["text"][:2000])])
                for h in history[-10:] if h.get("role") in ("user", "model") and h.get("text")]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=preface + question)]))

    for _ in range(MAX_STEPS):
        content = _turn(contents, toolset)
        contents.append(content)
        calls = [p.function_call for p in content.parts or [] if p.function_call]
        text = " ".join(p.text.strip() for p in content.parts or [] if p.text and not p.thought and p.text.strip())
        if not calls:
            yield {"type": "say", "text": text or "Sorry, I don't have an answer to that."}
            return
        # Independent tool calls run at the same time, so asking about two lenders isn't twice as slow.
        jobs = []
        for c in calls:
            args = dict(c.args or {})
            yield {"type": "tool", "name": c.name, "args": args, "label": _label(c.name, args)}
            fn = by_name.get(c.name)
            jobs.append((c, args, _pool.submit(fn, **args) if fn else None))
        responses = []
        for c, args, fut in jobs:
            try:
                out = fut.result(timeout=60) if fut else {"error": f"No tool named {c.name}."}
            except TypeError as e:
                out = {"error": f"Bad arguments: {e}"}
            except Exception as e:
                log.warning("assistant tool %s failed: %s", c.name, e)
                out = {"error": "That source could not be reached just now."}
            if isinstance(out, str):
                try:
                    out = json.loads(out)
                except ValueError:
                    out = {"result": out}
            yield {"type": "tool_done", "name": c.name, "summary": _summary(c.name, out)}
            if c.name == "open_page" and isinstance(out, dict) and out.get("url"):
                yield {"type": "link", "url": out["url"], "page": out["page"], "lender": args.get("lender", "")}
            responses.append(types.Part.from_function_response(name=c.name, response={"result": out}))
        contents.append(types.Content(role="user", parts=responses))
    yield {"type": "say", "text": "That took more steps than I allow. Try asking about one lender at a time."}
