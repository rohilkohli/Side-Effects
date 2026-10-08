"""Measure the Gemini classifier against hand-labelled complaints.

Runs pipeline/classify.py's coder on every story in genai_labels.csv (hand
labelled, one annotator) and reports precision / recall / F1 for harm codes,
accuracy of the primary code, and template detection. A keyword baseline is
reported alongside so the deck can show what Gen AI adds.

Usage: python pipeline/eval_classifier.py <evidence_dir>/genai_labels.csv [report.md]
"""
import csv
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from classify import code_one, system_prompt  # noqa: E402

KEYWORDS = {
    "A1": ["deferred interest", "promotional", "promo"], "A2": ["annual fee", "fee"], "A3": ["interest rate", "apr"],
    "A4": ["late fee"], "B1": ["not credited", "payment posted", "pending payment"], "B2": ["refund", "credit balance"],
    "B3": ["autopay", "charged twice", "double"], "C1": ["closed my account", "frozen", "suspended"],
    "C2": ["limit was reduced", "lowered my limit", "decreased"], "C4": ["verify my identity", "locked out"],
    "C5": ["cancel", "close the account"], "D1": ["fraud", "unauthorized"], "D2": ["dispute", "chargeback"],
    "D3": ["identity theft", "never applied", "opened in my name"], "E1": ["credit report", "reported late"],
    "E2": ["denied"], "F1": ["rewards", "points", "cash back"], "F2": ["told me", "promised", "misled"],
    "F3": ["insurance", "protection"], "G1": ["hardship"], "G2": ["owe more"], "G3": ["collection", "harass"],
    "H1": ["transferred", "no one", "customer service"], "H2": ["privacy", "shared my"],
    "I1": ["contractor", "installer", "merchant went out"], "X1": ["15 u.s.c", "fcra section", "opting out of any"],
}


def keyword_codes(text: str) -> set[str]:
    t = text.lower()
    return {c for c, kws in KEYWORDS.items() if any(k in t for k in kws)}


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def score(gold: list[set], pred: list[set]):
    tp = sum(len(g & p) for g, p in zip(gold, pred))
    fp = sum(len(p - g) for g, p in zip(gold, pred))
    fn = sum(len(g - p) for g, p in zip(gold, pred))
    return prf(tp, fp, fn)


def main():
    rows = list(csv.DictReader(open(sys.argv[1], newline="")))
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "eval_report.md")
    system = system_prompt()
    with ThreadPoolExecutor(8) as pool:
        coded = list(pool.map(lambda r: code_one(r["narrative"], system), rows))

    gold = [set(r["fae_codes"].split(";")) - {"X1"} for r in rows]
    gem = [set(c.codes) - {"X1"} for c in coded]
    kw = [keyword_codes(r["narrative"]) - {"X1"} for r in rows]
    gold_t = [r["primary_fae"] == "X1" for r in rows]
    gem_t = [c.is_template or c.primary == "X1" for c in coded]
    real = [i for i, t in enumerate(gold_t) if not t]

    g_p, g_r, g_f = score([gold[i] for i in real], [gem[i] for i in real])
    k_p, k_r, k_f = score([gold[i] for i in real], [kw[i] for i in real])
    prim = sum(coded[i].primary == rows[i]["primary_fae"] for i in real) / len(real)
    t_p, t_r, t_f = prf(sum(a and b for a, b in zip(gold_t, gem_t)), sum(b and not a for a, b in zip(gold_t, gem_t)),
                        sum(a and not b for a, b in zip(gold_t, gem_t)))
    misses = Counter(c for i in real for c in gold[i] - gem[i])

    report = f"""# Classifier evaluation

{len(rows)} hand-labelled CFPB complaints ({sum(gold_t)} templates, {len(real)} genuine). Single annotator.

| | Precision | Recall | F1 |
|---|---|---|---|
| Gemini, harm codes | {g_p:.2f} | {g_r:.2f} | {g_f:.2f} |
| Keyword baseline, harm codes | {k_p:.2f} | {k_r:.2f} | {k_f:.2f} |
| Gemini, template detection | {t_p:.2f} | {t_r:.2f} | {t_f:.2f} |

Gemini primary-code accuracy on genuine complaints: {prim:.0%}.
Most-missed codes: {", ".join(f"{c} ({n})" for c, n in misses.most_common(5)) or "none"}.
"""
    out.write_text(report)
    Path(out.with_suffix(".jsonl")).write_text("\n".join(json.dumps({"sid": r["sid"], **c.model_dump()}) for r, c in zip(rows, coded)))
    print(report)


if __name__ == "__main__":
    main()
