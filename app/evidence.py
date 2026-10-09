"""Signal store: the deterministic "pharmacovigilance" layer.

Every number on a leaflet comes from here, never from the language model.
The statistic is the proportional reporting ratio (PRR) that drug-safety
regulators use on adverse-event reports: how much more often a kind of
complaint appears in one company's complaints than in its peers'.
A line becomes a signal under the Evans rule (a>=3, PRR>=2, chi2>=4).
"""
from __future__ import annotations

import difflib
import json
import re
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).parent / "data"

BNPL_POOL = "BNPL_POOLED(Affirm Holdings, Inc+Klarna AB+Block, Inc.+Sezzle Inc.+Zip Co US Inc.+Paypal Holdings, Inc)"

# Brand names people see on a flyer -> the company name in the CFPB database.
ALIASES = {
    "apple card": "GOLDMAN SACHS BANK USA", "goldman": "GOLDMAN SACHS BANK USA", "marcus": "GOLDMAN SACHS BANK USA",
    "amex": "AMERICAN EXPRESS COMPANY", "american express": "AMERICAN EXPRESS COMPANY",
    "chase": "JPMORGAN CHASE & CO.", "jpmorgan": "JPMORGAN CHASE & CO.",
    "citi": "CITIBANK, N.A.", "citibank": "CITIBANK, N.A.", "costco anywhere": "CITIBANK, N.A.",
    "capital one": "CAPITAL ONE FINANCIAL CORPORATION", "quicksilver": "CAPITAL ONE FINANCIAL CORPORATION",
    "bank of america": "BANK OF AMERICA, NATIONAL ASSOCIATION",
    "wells fargo": "WELLS FARGO & COMPANY", "discover card": "DISCOVER BANK", "discover it": "DISCOVER BANK", "discover bank": "DISCOVER BANK",
    "synchrony": "SYNCHRONY FINANCIAL", "care credit": "SYNCHRONY FINANCIAL", "carecredit": "SYNCHRONY FINANCIAL",
    "amazon store card": "SYNCHRONY FINANCIAL",
    "bread financial": "Bread Financial Holdings, Inc.", "comenity": "Bread Financial Holdings, Inc.",
    "barclays": "BARCLAYS BANK DELAWARE", "barclaycard": "BARCLAYS BANK DELAWARE",
    "us bank": "U.S. BANCORP", "u.s. bank": "U.S. BANCORP", "td bank": "TD BANK US HOLDING COMPANY",
    "navy federal": "NAVY FEDERAL CREDIT UNION", "usaa": "UNITED SERVICES AUTOMOBILE ASSOCIATION",
    "truist": "TRUIST FINANCIAL CORPORATION", "chime": "Chime Financial Inc",
    "mission lane": "CLGF Holdco 1, LLC", "atlanticus": "Atlanticus Services Corporation",
    "aspire card": "Atlanticus Services Corporation", "fortiva": "Atlanticus Services Corporation",
    "imprint": "Imprint Payments, Inc.", "robinhood": "ROBINHOOD MARKETS INC.",
    "affirm": "Affirm Holdings, Inc", "klarna": "Klarna AB", "afterpay": "Block, Inc.", "cash app": "Block, Inc.",
    "block inc": "Block, Inc.", "sezzle": "Sezzle Inc.", "zip co": "Zip Co US Inc.", "zip pay": "Zip Co US Inc.",
    "quadpay": "Zip Co US Inc.", "paypal": "Paypal Holdings, Inc", "onemain": "OneMain Finance Corporation",
}

BNPL_COMPANIES = {"Affirm Holdings, Inc", "Klarna AB", "Block, Inc.", "Sezzle Inc.", "Zip Co US Inc.", "Paypal Holdings, Inc"}

PRIMARY = {"credit_card": "cc2024_issuers", "loan": "cfpb_api_all_dates_current_product_name"}
RECENT = "cc2026q3_issuers"
MIN_PEER_SIZE = 300  # companies with fewer complaints are too small to rank as alternatives


@lru_cache
def store() -> dict:
    return json.load(open(DATA / "signals.json"))


@lru_cache
def quotes() -> dict:
    return json.load(open(DATA / "quotes.json"))


@lru_cache
def vocabulary() -> list[dict]:
    return json.load(open(DATA / "vocabulary.json"))


def product_family(product_type: str) -> str:
    return "credit_card" if product_type == "credit_card" else "loan"


def companies(family: str | None = None) -> list[str]:
    rows = store()["rows"]
    return sorted({r["company"] for r in rows if (family is None or r["product"] == family) and r["company"] != BNPL_POOL})


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", s.lower()).strip()


def resolve_company(name: str | None, product_type: str = "credit_card") -> str | None:
    """Map a brand or issuer name as printed on a flyer to a CFPB company."""
    if not name:
        return None
    n = " " + _norm(name) + " "
    for alias in sorted(ALIASES, key=len, reverse=True):
        if f" {_norm(alias)} " in n:
            return ALIASES[alias]
    names = companies()
    exact = {_norm(c): c for c in names}
    if _norm(name) in exact:
        return exact[_norm(name)]
    match = difflib.get_close_matches(_norm(name), list(exact), n=1, cutoff=0.75)
    return exact[match[0]] if match else None


def _line(r: dict, scope: str, recent: dict | None = None) -> dict:
    line = {
        "id": f"{r['dataset']}:{r['level']}:{r['term']}",
        "label": r["label"],
        "cfpb_term": r["term"],
        "fae": r["fae"],
        "scope": scope,  # "bank" = this company's complaints; "product_class" = a whole product category
        "company": r["company"],
        "reported_x": round(r["prr"], 1),
        "ci95": [r["ci_low"], r["ci_high"]],
        "n": r["a"],
        "company_total": r["company_total"],
        "share_company": r["share_company"],
        "share_peers": r["share_peers"],
        "period": store()["datasets"][r["dataset"]]["period"],
        "dataset": r["dataset"],
        "status": "persisting",
    }
    rep = r.get("replication")
    if recent is not None:
        line["status"] = "emerging"
    elif rep is None:
        line["status"] = "single_period"
    elif rep["signal"]:
        line["status"] = "persisting"
        line["recent"] = {"period": store()["datasets"][RECENT]["period"], "reported_x": round(rep["prr"], 1), "n": rep["a"]}
    elif rep["ci_low"] and rep["ci_low"] > 1:
        line["status"] = "fading"
        line["recent"] = {"period": store()["datasets"][RECENT]["period"], "reported_x": round(rep["prr"], 1), "n": rep["a"]}
    else:
        line["status"] = "not_seen_recently"
    return line


def _dedupe(lines: list[dict]) -> list[dict]:
    """Prefer a specific sub-issue over its parent issue when both are signals."""
    sub_parents = {l["cfpb_term"].split(" || ")[0] for l in lines if " || " in l["cfpb_term"]}
    out = [l for l in lines if " || " in l["cfpb_term"] or l["cfpb_term"] not in sub_parents]
    seen, uniq = set(), []
    for l in sorted(out, key=lambda l: -l["reported_x"]):
        if l["label"] in seen:
            continue
        seen.add(l["label"])
        uniq.append(l)
    return uniq


def signals_for(company: str | None, product_type: str) -> dict:
    """All disproportionality signals that belong on this product's leaflet."""
    family = product_family(product_type)
    rows = store()["rows"]
    result = {"company": company, "family": family, "lines": [], "company_total": None, "matched": False}

    if company:
        own = [r for r in rows if r["company"] == company and r["product"] == family]
        primary = [r for r in own if r["dataset"] == PRIMARY[family]]
        recent = [r for r in own if r["dataset"] == RECENT]
        if not primary and family == "loan":
            # A BNPL lender with card complaints only in 2026: fall back to its card data.
            primary = [r for r in rows if r["company"] == company and r["dataset"] == RECENT]
        if primary or recent:
            result["matched"] = True
            result["company_total"] = (primary or recent)[0]["company_total"]
        lines = [_line(r, "bank") for r in primary if r["signal"]]
        primary_terms = {r["term"] for r in primary}
        if family == "credit_card":
            lines += [_line(r, "bank", recent=r) for r in recent if r["signal"] and r["term"] not in primary_terms]
        result["lines"] = _dedupe(lines)

    if product_type == "bnpl" or (company in BNPL_COMPANIES):
        pool = [r for r in rows if r["company"] == BNPL_POOL and r["signal"]]
        result["lines"] += [_line(r, "product_class") for r in pool]
    return result


LOAN_PRODUCT = "Payday loan, title loan, personal loan, or advance loan"


def quotes_for(company: str | None, cfpb_term: str, limit: int = 3, family: str | None = None) -> list[dict]:
    """Real anonymised complaint narratives behind a signal: same company, or same product family for a category signal."""
    issue, _, sub = cfpb_term.partition(" || ")
    out = []
    for q in quotes()["quotes"]:
        if company and q["company"] != company:
            continue
        if family and (q["product"] == LOAN_PRODUCT) != (family == "loan"):
            continue
        if q["issue"] == issue and (not sub or q["sub_issue"] == sub):
            out.append(q)
    return out[:limit]


def quotes_for_code(fae: str | None, limit: int = 3, family: str | None = None) -> list[dict]:
    """Stories coded with a side-effect code by the classifier (used where the official label is missing)."""
    if not fae:
        return []
    return [q for q in quotes()["quotes"] if fae in q["fae_codes"]
            and (family is None or (q["product"] == LOAN_PRODUCT) == (family == "loan"))][:limit]


def alternatives(company: str | None, product_type: str, labels: list[str], limit: int = 3) -> list[dict]:
    """'Consider a generic': similar-sized peers without the same signals."""
    family = product_family(product_type)
    ds = PRIMARY[family]
    rows = [r for r in store()["rows"] if r["dataset"] == ds and r["company"] != BNPL_POOL]
    by_company: dict[str, dict] = {}
    for r in rows:
        c = by_company.setdefault(r["company"], {"company": r["company"], "total": r["company_total"], "signals": set()})
        if r["signal"]:
            c["signals"].add(r["label"])
    cands = []
    for c in by_company.values():
        if c["company"] == company or c["total"] < MIN_PEER_SIZE:
            continue
        shared = len(c["signals"] & set(labels))
        cands.append({"company": c["company"], "complaints": c["total"], "shared_signals": shared,
                      "total_signals": len(c["signals"]),
                      "clear_of": [l for l in labels if l not in c["signals"]]})
    cands.sort(key=lambda c: (c["shared_signals"], c["total_signals"], -c["complaints"]))
    return cands[:limit]


def compare(company_a: str, company_b: str, product_type: str = "credit_card") -> list[dict]:
    """Side-by-side PRR for every complaint term two companies share."""
    ds = PRIMARY[product_family(product_type)]
    rows = [r for r in store()["rows"] if r["dataset"] == ds]
    a = {r["term"]: r for r in rows if r["company"] == company_a}
    b = {r["term"]: r for r in rows if r["company"] == company_b}
    out = []
    for term in sorted(set(a) & set(b)):
        if a[term]["signal"] or b[term]["signal"]:
            out.append({"side_effect": a[term]["label"], company_a: round(a[term]["prr"], 2), company_b: round(b[term]["prr"], 2)})
    return out


def dataset_notes() -> dict:
    q = quotes()
    return {
        "datasets": store()["datasets"],
        "labelled_narratives": q["labelled_total"],
        "templates_excluded": q["templates_excluded"],
        "rule": "Evans rule: at least 3 reports, PRR >= 2 and chi-square >= 4, with a 95% confidence interval.",
        "disclaimer": "Complaints are unverified reports, not proof that the product caused harm. "
                      "Numbers compare how often a kind of problem is reported relative to similar companies; "
                      "they are not the chance that it will happen to you.",
    }


@lru_cache
def apac() -> dict:
    path = DATA / "apac.json"
    return json.load(open(path)) if path.exists() else {}


def india_group(*names: str | None) -> str | None:
    """Which RBI reporting group an Indian card issuer belongs to."""
    members = apac().get("IN", {}).get("members", {})
    for name in names:
        if not name:
            continue
        n = " " + _norm(name) + " "
        # longest names first so "SBI Card" (NBFC) wins over "SBI" (public sector bank)
        pairs = sorted(((b, g) for g, banks in members.items() for b in banks), key=lambda p: -len(p[0]))
        for bank, group in pairs:
            if f" {_norm(bank)} " in n:
                return group
    return None


def india_disclosure(*names: str | None) -> dict | None:
    """The bank's own published complaint breakdown, when we have it."""
    india = apac().get("IN", {})
    disc, aliases = india.get("bank_disclosures", {}), india.get("disclosure_aliases", {})
    keys = sorted(list(disc) + list(aliases), key=len, reverse=True)
    for name in names:
        if not name or india_group(name) == "nbfc":  # e.g. "SBI Card" is a separate company from SBI
            continue
        n = " " + _norm(name) + " "
        for k in keys:
            if f" {_norm(k)} " in n:
                bank = aliases.get(k, k)
                return dict(disc[bank], bank=bank)
    return None


def local_evidence(jurisdiction: str, product_type: str, *names: str | None) -> dict | None:
    """Country-specific complaint evidence for APAC products (India: RBI Ombudsman per-card rates)."""
    india = apac().get("IN")
    if jurisdiction != "IN" or not india:
        return None
    group = india_group(*names)
    out = {"country": "India", "source": india["source"], "india_per_1000_cards": india["india_per_1000_cards"],
           "groups": [], "group": None, "note": "", "disclosure": india_disclosure(*names)}
    if product_type != "credit_card":
        return out if out["disclosure"] else None
    out["groups"] = list(india["credit_card_groups"].values())
    if group == "nbfc":
        out["note"] = (f"This issuer is a non-bank (NBFC). NBFC card issuers drew {india['nbfc_card_complaints']:,} "
                       "Ombudsman complaints, but the RBI publishes no per-card rate for them.")
    elif group:
        g = india["credit_card_groups"][group]
        out["group"] = g
        out["note"] = (f"{g['label']} drew {g['per_1000_cards']} Ombudsman complaints per 1,000 credit cards, "
                       f"{g['x_vs_india']}x the Indian average of {india['india_per_1000_cards']} "
                       f"({g['complaints']:,} complaints, {india['source']['period']}).")
    else:
        out["note"] = "We could not tell which RBI reporting group this issuer belongs to."
    return out
