"""APAC validation: Indian consumer-court orders about credit cards and digital loans.

Fetches orders through the Indian Kanoon API (needs an API token from
api.indiankanoon.org; their terms allow AI use), strips the HTML, and codes
each order with the same Gemini coder used on US complaints, plus the lender
named. The output is used to check whether US signals also appear in India.

Usage: INDIANKANOON_TOKEN=... python pipeline/apac/indian_kanoon.py out.jsonl [--pages 5]
Not yet run: the build environment could not reach api.indiankanoon.org.
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent))
from app import gemini  # noqa: E402
from classify import system_prompt  # noqa: E402

API = "https://api.indiankanoon.org"
QUERIES = ['"credit card" bank "deficiency in service" doctypes:consumer',
           '"buy now pay later" OR "digital lending" doctypes:consumer']


class Order(BaseModel):
    lender: str
    product: str
    codes: list[str]
    primary: str
    upheld: bool


def post(path: str) -> dict:
    req = urllib.request.Request(API + path, method="POST",
                                 headers={"Authorization": f"Token {os.environ['INDIANKANOON_TOKEN']}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--pages", type=int, default=5)
    a = ap.parse_args()
    system = system_prompt() + "\nAlso name the lender, the product, and whether the forum ruled for the consumer (upheld)."
    with open(a.out, "w") as out:
        for q in QUERIES:
            for page in range(a.pages):
                res = post(f"/search/?formInput={urllib.parse.quote(q)}&pagenum={page}")
                for d in res.get("docs", []):
                    body = post(f"/doc/{d['tid']}/").get("doc", "")
                    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
                    order = gemini.generate_json(f"CONSUMER COURT ORDER:\n{text[:20000]}", Order, system=system, temperature=0)
                    out.write(json.dumps({"tid": d["tid"], "title": d.get("title"), "date": d.get("publishdate"),
                                          **order.model_dump()}) + "\n")


if __name__ == "__main__":
    main()
