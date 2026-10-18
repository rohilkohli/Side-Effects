"""Safety alerts: the pharmacovigilance loop, run on live data.

Drug regulators watch incoming adverse-event reports, spot a problem that is suddenly reported more
often, publish a safety alert and update the label. This module does the same for credit:

  1. Scan     (code)    the CFPB's live complaint feed for each lender: last 45 days vs the 180 days before
  2. Detect   (code)    a time-PRR per issue (is it a bigger share of complaints than it used to be?) plus
                        a volume check, with the same thresholds style as the main statistics
  3. Explain  (Gemini)  Google Search for a cause, then plain-words alert text around the fixed numbers
  4. Record   (BigQuery) every alert is written to side_effects.safety_alerts
  5. Act      (code)    the gate, the leaflets, the assistant and the MCP server read active alerts at once

Detection and the gate's use of an alert are deterministic; Gemini only writes the words.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Iterator

from . import bq, evidence, gemini, live, profiles
from .schemas import AlertText

log = logging.getLogger("side_effects.alerts")

RECENT_DAYS, BASELINE_DAYS = 45, 180
MIN_REPORTS, MIN_RATIO, MIN_CHI2 = 10, 2.0, 4.0      # an issue must clear all three to raise an alert
VOLUME_RATIO, MIN_VOLUME = 1.5, 100                  # complaints per day up by half, on real volume
ACTIVE_DAYS = 30                                     # an alert stays on leaflets and in the gate this long
RESCAN_SECONDS = 3600                                # the public scan endpoint runs at most hourly
WATCHLIST = [  # the largest card issuers in the complaint data, plus pay-later lenders
    ("CAPITAL ONE FINANCIAL CORPORATION", "credit_card"), ("CITIBANK, N.A.", "credit_card"),
    ("SYNCHRONY FINANCIAL", "credit_card"), ("JPMORGAN CHASE & CO.", "credit_card"),
    ("AMERICAN EXPRESS COMPANY", "credit_card"), ("BANK OF AMERICA, NATIONAL ASSOCIATION", "credit_card"),
    ("Bread Financial Holdings, Inc.", "credit_card"), ("DISCOVER BANK", "credit_card"),
    ("WELLS FARGO & COMPANY", "credit_card"), ("GOLDMAN SACHS BANK USA", "credit_card"),
    ("BARCLAYS BANK DELAWARE", "credit_card"), ("Affirm Holdings, Inc", "bnpl"), ("Klarna AB", "bnpl"),
    ("Paypal Holdings, Inc", "bnpl"), ("Block, Inc.", "bnpl"),
]
TABLE = "safety_alerts"

WRITER_SYSTEM = """You write safety alerts for SIDE EFFECTS, in the style of a medicines regulator's safety
communication, for ordinary customers. Use only the numbers you are given; never add a number. Complaints
are unverified reports, so say "reported" not "happened". Do not tell anyone to sign or not to sign."""

_alerts: dict[str, dict] = {}
_lock = threading.Lock()
_last_scan: dict = {}
_scanning = threading.Lock()


def _issue_map() -> dict[str, tuple[str, str]]:
    """CFPB issue name -> (side-effect code, plain label), from our own vocabulary of complaint terms."""
    out: dict[str, tuple[str, str]] = {}
    for r in evidence.store()["rows"]:
        if r.get("fae") and "||" not in r["term"]:
            out.setdefault(r["term"], (r["fae"], r["label"]))
    return out


def affected_profiles(fae: str | None) -> list[str]:
    return [k for k, p in profiles.PROFILES.items() if fae and fae in p["codes"]]


def _chi2(a: int, b: int, c: int, d: int) -> float:
    """Yates-corrected chi-squared for the 2x2 table, as used for PRR signals."""
    n = a + b + c + d
    den = (a + b) * (c + d) * (a + c) * (b + d)
    return 0.0 if not den else n * max(0.0, abs(a * d - b * c) - n / 2) ** 2 / den


def _issues(body: dict) -> dict[str, int]:
    buckets = (body.get("aggregations", {}).get("issue", {}).get("issue", {}) or {}).get("buckets", [])
    return {b["key"]: int(b["doc_count"]) for b in buckets}


def detect(company: str, product_type: str, today: date | None = None) -> dict:
    """Compare a lender's last 45 days of complaints with the 180 days before. Pure statistics, no model."""
    today = today or date.today()
    cut, start = today - timedelta(days=RECENT_DAYS), today - timedelta(days=RECENT_DAYS + BASELINE_DAYS)
    recent = live._cfpb({"company": company, "date_received_min": cut.isoformat(), "size": 0})
    base = live._cfpb({"company": company, "date_received_min": start.isoformat(), "date_received_max": cut.isoformat(), "size": 0})
    r_tot, b_tot = live._total(recent), live._total(base)
    r_iss, b_iss = _issues(recent), _issues(base)
    names = _issue_map()
    signals = []
    for issue, a in r_iss.items():
        c = b_iss.get(issue, 0)
        b, d = r_tot - a, b_tot - c
        if a < MIN_REPORTS or not b_tot or not r_tot:
            continue
        ratio = (a / r_tot) / (max(c, 0.5) / b_tot)
        chi2 = _chi2(a, b, c, d)
        if ratio >= MIN_RATIO and chi2 >= MIN_CHI2:
            fae, label = names.get(issue, (None, issue))
            signals.append({"kind": "issue_rising", "issue": issue, "label": label, "fae": fae, "recent_n": a,
                            "baseline_n": c, "ratio": round(ratio, 1), "chi2": round(chi2, 1),
                            "share_now_pct": round(100 * a / r_tot, 1), "share_before_pct": round(100 * c / b_tot, 1)})
    per_day_now, per_day_before = r_tot / RECENT_DAYS, (b_tot / BASELINE_DAYS if b_tot else 0)
    if r_tot >= MIN_VOLUME and per_day_before and per_day_now / per_day_before >= VOLUME_RATIO:
        signals.append({"kind": "volume_rising", "issue": "All complaints", "label": "Complaints rising overall", "fae": None,
                        "recent_n": r_tot, "baseline_n": b_tot, "ratio": round(per_day_now / per_day_before, 1), "chi2": None,
                        "per_day_now": round(per_day_now, 1), "per_day_before": round(per_day_before, 1)})
    signals.sort(key=lambda s: -s["ratio"])
    return {"company": company, "product_type": product_type, "recent_total": r_tot, "baseline_total": b_tot,
            "window": {"recent_from": cut.isoformat(), "baseline_from": start.isoformat(), "to": today.isoformat()},
            "signals": signals[:3]}


def _numbers(company: str, s: dict) -> str:
    if s["kind"] == "volume_rising":
        return (f"{company}: {s['recent_n']:,} complaints in the last {RECENT_DAYS} days, {s['per_day_now']} a day, "
                f"against {s['per_day_before']} a day in the {BASELINE_DAYS} days before ({s['ratio']} times the earlier rate).")
    return (f"{company}: '{s['label']}' (CFPB issue: {s['issue']}) is {s['share_now_pct']}% of complaints in the last "
            f"{RECENT_DAYS} days ({s['recent_n']} complaints), up from {s['share_before_pct']}% in the {BASELINE_DAYS} days "
            f"before ({s['baseline_n']}): {s['ratio']} times its earlier share.")


def explain(company: str, product_type: str, s: dict, window: dict) -> dict:
    """Gemini looks for a reason in the news (Google Search), then writes the alert around the fixed numbers."""
    facts = _numbers(company, s)
    note, sources = "", []
    try:
        note, sources, _ = live.grounded(
            f"Today is {date.today().isoformat()}. Complaints to the US regulator show this change: {facts} "
            f"Search the news from the last six months for a likely reason (a policy change, outage, system migration, "
            f"lawsuit, regulator action or fee change at {company}). Say plainly if you find nothing that explains it.")
    except gemini.LLMUnavailable:
        raise
    except Exception as e:
        log.info("alert news search failed for %s: %s", company, e)
    text = gemini.generate_json(f"Facts (use only these numbers):\n{facts}\n\nNews note (may be empty):\n<<<\n{note[:4000]}\n>>>",
                                AlertText, system=WRITER_SYSTEM)
    day = window["to"]
    aid = hashlib.sha1(f"{company}|{s['issue']}|{day}".encode()).hexdigest()[:12]
    return {"id": aid, "ts": datetime.now(timezone.utc).isoformat(), "date": day, "company": company,
            "product_type": product_type, "kind": s["kind"], "issue": s["issue"], "label": s["label"], "fae": s["fae"],
            "affects": affected_profiles(s["fae"]), "ratio": s["ratio"], "recent_n": s["recent_n"],
            "baseline_n": s["baseline_n"], "facts": facts, "headline": text.headline.strip()[:120],
            "what_changed": text.what_changed.strip()[:400], "who_should_care": text.who_should_care.strip()[:300],
            "what_to_do": text.what_to_do.strip()[:400], "possible_cause": text.possible_cause.strip()[:300],
            "sources": sources[:5] if text.possible_cause.strip() else [], "window": window}


def _store(alert: dict) -> None:
    with _lock:
        _alerts[alert["id"]] = alert
    bq.insert(TABLE, {k: (json.dumps(v) if k in ("sources", "window") else v) for k, v in alert.items()})


def active(company: str | None = None) -> list[dict]:
    """Alerts from the last 30 days, newest first; for one lender when company is given."""
    since = (date.today() - timedelta(days=ACTIVE_DAYS)).isoformat()
    with _lock:
        out = [a for a in _alerts.values() if a["date"] >= since and (company is None or a["company"] == company)]
    return sorted(out, key=lambda a: (a["date"], a["ratio"]), reverse=True)


def for_name(name: str, product_type: str = "credit_card") -> list[dict]:
    company = evidence.resolve_company(name, product_type)
    return active(company) if company else []


def load() -> None:
    """Read recent alerts back from BigQuery when the service starts, so a restart forgets nothing."""
    for row in bq.recent_rows(TABLE, days=ACTIVE_DAYS):
        for k in ("sources", "window"):
            try:
                row[k] = json.loads(row.get(k) or ("[]" if k == "sources" else "{}"))
            except (TypeError, ValueError):
                row[k] = [] if k == "sources" else {}
        row["affects"] = list(row.get("affects") or [])
        row["ts"] = str(row.get("ts") or "")
        with _lock:
            _alerts.setdefault(row["id"], row)


def scan(watchlist: list[tuple[str, str]] | None = None, force: bool = False) -> Iterator[dict]:
    """Run the whole loop and stream what happens, lender by lender."""
    if not force and _last_scan and time.time() - _last_scan["at"] < RESCAN_SECONDS:
        yield {"type": "recent", "minutes_ago": int((time.time() - _last_scan["at"]) / 60), **_last_scan["summary"],
               "alerts": active()}
        return
    if not _scanning.acquire(blocking=False):
        yield {"type": "busy", "text": "A scan is already running. Try again in a minute."}
        return
    try:
        lenders = watchlist or WATCHLIST
        yield {"type": "scan_start", "lenders": len(lenders), "recent_days": RECENT_DAYS, "baseline_days": BASELINE_DAYS}
        found, failed = [], 0
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [(c, pt, pool.submit(detect, c, pt)) for c, pt in lenders]
            for c, pt, fut in futures:
                try:
                    d = fut.result(timeout=40)
                except Exception as e:
                    log.warning("scan of %s failed: %s", c, e)
                    failed += 1
                    yield {"type": "lender", "company": c, "error": True}
                    continue
                yield {"type": "lender", "company": c, "recent_total": d["recent_total"],
                       "signals": [{"label": s["label"], "ratio": s["ratio"], "kind": s["kind"]} for s in d["signals"]]}
                found += [(d, s) for s in d["signals"]]
        new = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            # The strongest spikes first, issue spikes before plain volume rises; at most six alerts a scan.
            ranked = sorted(found, key=lambda ds: (ds[1]["kind"] != "issue_rising", -ds[1]["ratio"]))[:6]
            jobs = [(d, s, pool.submit(explain, d["company"], d["product_type"], s, d["window"])) for d, s in ranked]
            for d, s, fut in jobs:
                yield {"type": "writing", "company": d["company"], "label": s["label"]}
                try:
                    alert = fut.result(timeout=90)
                except gemini.LLMUnavailable:
                    raise
                except Exception as e:
                    log.warning("alert writing failed: %s", e)
                    continue
                _store(alert)
                new.append(alert)
                yield {"type": "alert", "alert": alert}
        summary = {"lenders": len(lenders), "failed": failed, "signals": len(found), "alerts_written": len(new)}
        _last_scan.update(at=time.time(), summary=summary)
        yield {"type": "scan_end", **summary, "alerts": active()}
    finally:
        _scanning.release()
