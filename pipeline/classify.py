"""Harvest stage: Gemini codes complaint stories into the side-effect vocabulary.

Official complaint labels are coarse ("Problem with fees"), often wrong, and
about a fifth of stories are copy-paste credit-repair templates that create
false signals. Gemini reads each story, flags templates, and assigns every
specific harm it describes. The coded table then feeds the PRR statistics
(pipeline/bigquery/prr.sql).

Usage:
  python pipeline/classify.py complaints.csv out.jsonl [--text-col narrative] [--id-col complaint_id] [--limit N]
For hundreds of thousands of rows use the BigQuery version (pipeline/bigquery/classify.sql).
"""
import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent))
from app import evidence, gemini  # noqa: E402


class Coding(BaseModel):
    is_template: bool = Field(description="True if the text is a generic credit-repair or legal template with no product-specific facts.")
    codes: list[str] = Field(description="Every vocabulary code for a harm the story describes, most important first. Empty if template.")
    primary: str = Field(description="The single most important code, or X1 for a template.")


def system_prompt() -> str:
    vocab = "\n".join(f"{v['code']} {v['preferred_term']}: {v['definition']} (e.g. {v['example_trigger']})"
                      for v in evidence.vocabulary())
    return ("You code consumer complaints about credit products into a fixed vocabulary of financial side effects, "
            "the way drug-safety staff code adverse-event reports. Code what happened to the person, not the label "
            "they chose. Only use codes from this list:\n" + vocab)


def code_one(text: str, system: str) -> Coding:
    return gemini.generate_json(f"COMPLAINT:\n{text[:6000]}", Coding, system=system, temperature=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--text-col", default="narrative"); ap.add_argument("--id-col", default="complaint_id")
    ap.add_argument("--limit", type=int, default=0); ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    rows = list(csv.DictReader(open(a.src, newline="")))
    rows = rows[:a.limit] if a.limit else rows
    system = system_prompt()
    with ThreadPoolExecutor(a.workers) as pool, open(a.out, "w") as out:
        for row, coding in zip(rows, pool.map(lambda r: code_one(r[a.text_col], system), rows)):
            out.write(json.dumps({"id": row[a.id_col], **coding.model_dump()}) + "\n")
    print(f"coded {len(rows)} complaints -> {a.out}")


if __name__ == "__main__":
    main()
