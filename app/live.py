"""Live check on a lender: the regulator's complaint feed right now, and recent news found by Gemini
with Google Search.

The complaint numbers come straight from the CFPB's public API, counted by the CFPB. The news is
found and summarised by Gemini, grounded in Google Search, and every source it used is listed so a
person can read it themselves. Nothing here changes the gate's verdict.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta

from . import bq, evidence, gemini
from .schemas import NewsReport

log = logging.getLogger("side_effects.live")

CFPB_API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
WINDOW_DAYS = 90
CACHE_SECONDS = 3600
_cache: dict[tuple, tuple[float, dict]] = {}


def _cached(key: tuple, make):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_SECONDS:
        return hit[1]
    out = make()
    if out.get("available"):
        _cache[key] = (time.time(), out)
    return out


def _cfpb(params: dict) -> dict:
    url = CFPB_API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "side-effects/1.0 (consumer-protection prototype)",
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.load(r)


def _total(body: dict) -> int:
    t = body.get("hits", {}).get("total", 0)
    return int(t.get("value", 0) if isinstance(t, dict) else t)


def complaints(company: str) -> dict:
    """Complaints the CFPB received about this company in the last 90 days, the 90 days before, and the top issues."""
    def make():
        today = date.today()
        start, prev = today - timedelta(days=WINDOW_DAYS), today - timedelta(days=2 * WINDOW_DAYS)
        try:
            now = _cfpb({"company": company, "date_received_min": start.isoformat(), "size": 0})
            before = _cfpb({"company": company, "date_received_min": prev.isoformat(),
                            "date_received_max": start.isoformat(), "size": 0, "no_aggs": "true"})
            newest = _cfpb({"company": company, "size": 1, "sort": "created_date_desc", "no_aggs": "true"})
        except Exception as e:
            log.warning("CFPB live API failed: %s", e)
            return {"available": False}
        buckets = (now.get("aggregations", {}).get("issue", {}).get("issue", {}) or {}).get("buckets", [])
        hits = newest.get("hits", {}).get("hits", [])
        latest = (hits[0].get("_source", {}).get("date_received", "") if hits else "")[:10]
        n_now, n_before = _total(now), _total(before)
        return {"available": True, "company": company, "window_days": WINDOW_DAYS,
                "last_90_days": n_now, "previous_90_days": n_before,
                "change_pct": round((n_now - n_before) / n_before * 100) if n_before else None,
                "latest_complaint": latest,
                "top_issues": [{"issue": b["key"], "n": int(b["doc_count"])} for b in buckets[:4]],
                "source": "CFPB Consumer Complaint Database, live API"}
    return _cached(("cfpb", company), make)


NEWS_PROMPT = """Search the web for news from the last 12 months (today is {today}) about {name}{also}
as a lender to consumers{product}. Look for: regulator fines, orders or investigations; lawsuits and
class actions; outages that stopped payments or cards; data breaches; changes to rates, fees or terms
that hurt customers. Ignore share price, earnings and executive news. For each item give the date, what
happened, which publication or regulator reported it, and what it means for someone about to sign up.
If you find nothing relevant, say so plainly."""

STRUCTURE_SYSTEM = """You turn a news research note into a list. Keep only items the note actually
contains, with their dates and sources as written. Never add facts. If the note found nothing, return
no items and say so in the summary."""


def _grounded_research(name: str, company: str | None, product_type: str) -> tuple[str, list[dict], list[str]]:
    from google.genai import types

    also = f" (in US complaint records: {company})" if company and company.lower() not in name.lower() else ""
    product = {"credit_card": ", especially its credit cards", "bnpl": ", especially buy now pay later"}.get(product_type, "")
    prompt = NEWS_PROMPT.format(today=date.today().isoformat(), name=name, also=also, product=product)

    def call():
        resp = gemini.client().models.generate_content(
            model=gemini.FAST_MODEL, contents=prompt,
            config=types.GenerateContentConfig(tools=[types.Tool(google_search=types.GoogleSearch())]))
        if not resp.text:
            raise gemini.LLMEmpty("no research text")
        return resp

    resp = gemini.with_retries(call)
    sources, seen = [], set()
    meta = resp.candidates[0].grounding_metadata if resp.candidates else None
    for ch in (getattr(meta, "grounding_chunks", None) or []):
        web = getattr(ch, "web", None)
        if web and web.uri and web.uri not in seen:
            seen.add(web.uri)
            sources.append({"title": (web.title or web.domain or "Source")[:120], "url": web.uri})
    queries = list(getattr(meta, "web_search_queries", None) or []) if meta else []
    return resp.text, sources[:8], queries[:4]


def news(name: str, product_type: str = "credit_card") -> dict:
    """Recent news about a lender, researched by Gemini with Google Search and then structured."""
    name = re.sub(r"\s+", " ", name).strip()[:80]
    company = evidence.resolve_company(name, product_type)

    def make():
        try:
            text, sources, queries = _grounded_research(name, company, product_type)
            got = gemini.generate_json(f"Research note:\n<<<\n{text[:8000]}\n>>>", NewsReport, system=STRUCTURE_SYSTEM)
        except gemini.LLMUnavailable:
            return {"available": False, "reason": "Gemini is not configured."}
        except Exception as e:
            log.warning("live news failed: %s", e)
            return {"available": False, "reason": "Google Search could not be reached just now. Try again in a minute."}
        items = [{"headline": i.headline.strip()[:140], "date": i.date.strip()[:20], "kind": i.kind.value,
                  "what_it_means": i.what_it_means.strip()[:260], "source": i.source.strip()[:80]} for i in got.items[:6]]
        items.sort(key=lambda i: i["date"], reverse=True)
        return {"available": True, "name": name, "items": items, "summary": got.summary.strip()[:400],
                "sources": sources, "searched": queries, "grounded": bool(sources)}
    return _cached(("news", name.lower(), product_type), make)


def check(name: str, product_type: str = "credit_card") -> dict:
    """What SIDE EFFECTS knows about a lender: our statistics, plus the live complaint feed."""
    company = evidence.resolve_company(name, product_type)
    sig = evidence.signals_for(company, product_type) if company else {"lines": []}
    feed = complaints(company) if company else {"available": False}
    archive = bq.lender_snapshot(company, product_type) if company and not feed.get("available") else {"available": False}
    return {"name": name, "company": company, "product_type": product_type,
            "signals": [{"label": l["label"], "reported_x": l["reported_x"], "scope": l["scope"]} for l in sig["lines"]][:5],
            "complaints": feed, "archive": archive}
