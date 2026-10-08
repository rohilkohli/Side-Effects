"""Build the app's evidence files from the pipeline outputs.

Inputs (the outputs of the harvest + signal stages, see pipeline/README.md):
  prr_signals.csv   company x complaint-term disproportionality table
  genai_labels.csv  complaint narratives coded into the side-effect vocabulary
  fae_vocabulary.csv the side-effect vocabulary

Usage: python pipeline/build_data.py <evidence_dir> [out_dir]
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from taxonomy import plain  # noqa: E402

DATASETS = {
    "cc2024_issuers": {
        "product": "credit_card",
        "period": "Jan-Dec 2024",
        "description": "All 75,989 US CFPB credit-card complaints received in 2024; credit bureaus removed from the peer group (53,978 issuer complaints).",
    },
    "cc2026q3_issuers": {
        "product": "credit_card",
        "period": "Jun-Sep 2026",
        "description": "21,293 US CFPB credit-card complaints received 28 Jun-28 Sep 2026; credit bureaus removed.",
    },
    "cfpb_api_all_dates_current_product_name": {
        "product": "loan",
        "period": "2017-Sep 2026 (93% from 2024-2026)",
        "description": "US CFPB 'payday, title, personal loan or advance' complaints (38,988), which is where BNPL complaints are filed.",
    },
}


def num(v, cast=float):
    return cast(v) if v not in ("", None) else None


def build(src: Path, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in csv.DictReader(open(src / "prr_signals.csv", newline="")):
        if r["prr"] == "":  # no complaints of this kind at the company: nothing to compare
            continue
        label, fae = plain(r["term"])
        rows.append({
            "dataset": r["dataset"],
            "product": DATASETS[r["dataset"]]["product"],
            "level": r["level"],
            "company": r["company"],
            "term": r["term"],
            "label": label,
            "fae": fae,
            "a": int(r["a_company_term"]),
            "company_total": int(r["company_total"]),
            "peer_a": int(r["c_others_term"]),
            "peer_total": int(r["c_others_term"]) + int(r["d_others_other"]),
            "share_company": float(r["share_company"]),
            "share_peers": float(r["share_others"]),
            "prr": float(r["prr"]),
            "ci_low": num(r["ci95_low"]),
            "ci_high": num(r["ci95_high"]),
            "chi2": num(r["chi2_yates"]),
            "signal": r["signal_evans"] == "1",
            "replication": None if r["replication_2026q3_a"] == "" else {
                "a": num(r["replication_2026q3_a"], int),
                "prr": num(r["replication_2026q3_prr"]),
                "ci_low": num(r["replication_2026q3_ci95_low"]),
                "signal": r["replication_2026q3_signal_evans"] == "1",
            },
        })
    json.dump({"datasets": DATASETS, "rows": rows}, open(out / "signals.json", "w"), separators=(",", ":"))

    vocab = [dict(r) for r in csv.DictReader(open(src / "fae_vocabulary.csv", newline=""))]
    json.dump(vocab, open(out / "vocabulary.json", "w"), indent=1)

    quotes, templates, total = [], 0, 0
    for r in csv.DictReader(open(src / "genai_labels.csv", newline="")):
        total += 1
        if r["primary_fae"] == "X1":
            templates += 1
            continue
        text = " ".join(r["narrative"].split())
        quotes.append({
            "complaint_id": r["cfpb_complaint_id"],
            "date": r["date_received"][:10],
            "company": r["cfpb_company"],
            "product": r["cfpb_product"],
            "issue": r["cfpb_issue"],
            "sub_issue": r["cfpb_sub_issue"],
            "fae_codes": r["fae_codes"].split(";") if r["fae_codes"] else [],
            "official_label_fit": r["cfpb_fit"],
            "text": text[:420] + ("…" if len(text) > 420 else ""),
        })
    json.dump({"labelled_total": total, "templates_excluded": templates, "quotes": quotes},
              open(out / "quotes.json", "w"), indent=0)
    print(f"{len(rows)} signal rows, {len(vocab)} terms, {len(quotes)} quotes ({templates} templates excluded)")


if __name__ == "__main__":
    build(Path(sys.argv[1]), Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).parent.parent / "app" / "data"))
