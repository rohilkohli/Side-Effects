"""SIDE EFFECTS web service (FastAPI, runs on Cloud Run)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import evidence, gemini, pipeline, profiles
from .agents import pharmacist

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "static"
SAMPLES = ROOT / "samples"
MAX_UPLOAD = 20 * 1024 * 1024

log = logging.getLogger("side_effects")
app = FastAPI(title="SIDE EFFECTS", description="Pharmacovigilance for money: a side-effects leaflet for credit products.")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/meta")
def meta():
    return {
        "profiles": [{"key": k, "label": v["label"]} for k, v in profiles.PROFILES.items()],
        "companies": evidence.companies(),
        "samples": sorted(p.stem for p in SAMPLES.glob("*.txt")),
        "evidence": evidence.dataset_notes(),
    }


@app.get("/api/samples/{name}")
def sample(name: str):
    path = SAMPLES / f"{name}.txt"
    if path.parent != SAMPLES or not path.exists():
        raise HTTPException(404)
    return {"name": name, "text": path.read_text()}


@app.post("/api/leaflet")
async def make_leaflet(
    images: list[UploadFile] = File(default=[]),
    contract: UploadFile | None = File(default=None),
    contract_text: str = Form(default=""),
    flyer_text: str = Form(default=""),
    issuer: str = Form(default=""),
    product_type: str = Form(default=""),
    profile: str = Form(default=""),
    note: str = Form(default=""),
):
    imgs = []
    for f in images:
        data = await f.read()
        if data:
            if len(data) > MAX_UPLOAD:
                raise HTTPException(413, "Image too large")
            imgs.append((data, f.content_type or "image/jpeg"))
    pdf = None
    if contract is not None:
        data = await contract.read()
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "Contract too large")
        if data and (contract.content_type == "application/pdf" or data[:4] == b"%PDF"):
            pdf = data
        elif data:
            contract_text = data.decode("utf-8", "replace")
    inp = pipeline.Inputs(
        images=imgs, contract_pdf=pdf, contract_text=contract_text, issuer_override=issuer,
        product_type_override=product_type if product_type in {"credit_card", "bnpl", "personal_loan"} else "",
        profile=[p for p in profile.split(",") if p], note=note[:500], flyer_text=flyer_text[:4000],
    )
    def stream():
        try:
            for event in pipeline.run(inp):
                yield json.dumps(event) + "\n"
        except gemini.LLMUnavailable as e:
            yield json.dumps({"step": "error", "status": "error", "detail": f"Gemini is not configured: {e}"}) + "\n"
        except Exception as e:  # surface failures to the UI instead of a broken stream
            log.exception("pipeline failed")
            yield json.dumps({"step": "error", "status": "error", "detail": f"Something went wrong: {type(e).__name__}"}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


class Ask(BaseModel):
    leaflet_id: str
    question: str
    history: list[dict] = []


@app.post("/api/pharmacist")
def ask_pharmacist(body: Ask):
    leaflet = pipeline.LEAFLETS.get(body.leaflet_id)
    if not leaflet:
        raise HTTPException(404, "Leaflet expired; please make it again.")
    try:
        text = pharmacist.answer(leaflet, pipeline.CONTRACTS.get(body.leaflet_id, []), body.history, body.question[:1000])
    except gemini.LLMUnavailable as e:
        raise HTTPException(503, str(e))
    return {"answer": text}


# ---------------------------------------------------------------------------
# Machine-readable leaflets for AI agents that apply for credit on someone's behalf.
# ---------------------------------------------------------------------------

@app.get("/.well-known/side-effects.json")
def descriptor():
    return {
        "name": "SIDE EFFECTS",
        "description": "Side-effects leaflets for consumer credit products. Agents acting for a person should call "
                       "the check endpoint before committing them to a credit product, and show the person every "
                       "required disclosure.",
        "check": {"method": "POST", "path": "/api/v1/check",
                  "body": {"issuer": "string", "product_type": "credit_card|bnpl|personal_loan",
                           "applicant_profile": list(profiles.PROFILES)}},
        "leaflet": {"method": "GET", "path": "/api/v1/leaflets/{id}"},
        "verdicts": {"no_signal": "no disproportionate complaint signal found",
                     "disclose": "show the listed side effects to the person before signing",
                     "human_review": "a side effect matches the person's situation; the person must confirm"},
    }


@app.get("/api/v1/leaflets/{lid}")
def leaflet_json(lid: str):
    leaflet = pipeline.LEAFLETS.get(lid)
    if not leaflet:
        raise HTTPException(404)
    return leaflet


class Check(BaseModel):
    issuer: str
    product_type: str = "credit_card"
    applicant_profile: list[str] = []


@app.post("/api/v1/check")
def agent_check(body: Check):
    """Deterministic gate for agents: no language model in the loop, same answer every time."""
    company = evidence.resolve_company(body.issuer, body.product_type)
    sig = evidence.signals_for(company, body.product_type)
    sensitive = profiles.sensitive_codes(body.applicant_profile)
    disclosures, matches = [], []
    for l in sig["lines"]:
        level = "bank-level complaint signal" if l["scope"] == "bank" else "product-category complaint signal"
        text = (f"{l['label']}: reported {l['reported_x']}x more often than at peer lenders "
                f"({l['n']:,} complaints, {l['period']}; {level}; unverified reports).")
        disclosures.append({"side_effect": l["label"], "fae_code": l["fae"], "reported_x": l["reported_x"],
                            "ci95": l["ci95"], "n": l["n"], "level": l["scope"], "text": text})
        if l["fae"] in sensitive:
            matches.append(l["label"])
    verdict = "human_review" if matches else ("disclose" if disclosures else "no_signal")
    return JSONResponse({
        "issuer_matched": company,
        "verdict": verdict,
        "matches_applicant_situation": matches,
        "required_disclosures": disclosures,
        "disclaimer": evidence.dataset_notes()["disclaimer"],
    })


app.mount("/static", StaticFiles(directory=STATIC), name="static")
