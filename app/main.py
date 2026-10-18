"""SIDE EFFECTS web service (FastAPI, runs on Cloud Run)."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import evidence, gate, gemini, pipeline, profiles
from .agents import pharmacist, shopper

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "static"
SAMPLES = ROOT / "samples"
MAX_UPLOAD = 20 * 1024 * 1024

log = logging.getLogger("side_effects")
app = FastAPI(title="SIDE EFFECTS", description="Pharmacovigilance for money: a side-effects leaflet for credit products.")


def _ndjson(events) -> StreamingResponse:
    """Stream events as NDJSON, turning failures into an error event the UI can show."""
    def stream():
        try:
            for event in events:
                yield json.dumps(event) + "\n"
        except gemini.LLMUnavailable as e:
            yield json.dumps({"step": "error", "type": "error", "status": "error",
                              "detail": f"Gemini is not configured: {e}"}) + "\n"
        except Exception as e:  # surface failures to the UI instead of a broken stream
            log.exception("stream failed")
            from google.genai import errors as genai_errors
            detail = (f"Gemini refused the request ({e.code}): {e.message}" if isinstance(e, genai_errors.APIError)
                      else f"Something went wrong: {type(e).__name__}")
            yield json.dumps({"step": "error", "type": "error", "status": "error", "detail": detail}) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/version")
def version():
    """Which build is live, so a redeploy can be confirmed from the page footer."""
    v = ROOT / "app" / "VERSION"
    return {"version": v.read_text().strip() if v.exists() else "dev"}


@app.get("/")
def index():
    return FileResponse(STATIC / "agent.html")


@app.get("/leaflet")
def leaflet_page():
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
    return _ndjson(pipeline.run(inp))


class CustomPersona(BaseModel):
    name: str = "You"
    about: str = ""
    profile: list[str] = []


class AgentRun(BaseModel):
    persona: str = "maya"
    gated: bool = True
    hacked: bool = False
    custom: CustomPersona | None = None


@app.post("/api/agent/run")
def agent_run(body: AgentRun):
    """A Gemini shopping agent checks out for a person, live, with or without the SIDE EFFECTS gate."""
    custom = None
    if body.custom:
        custom = {"name": body.custom.name.strip()[:30] or "You", "about": body.custom.about.strip()[:300],
                  "profile": [k for k in body.custom.profile if k in profiles.PROFILES], "task": shopper.DEFAULT_TASK}
    return _ndjson(shopper.run(body.persona, body.gated, custom=custom, hacked=body.hacked))


class ReadMe(BaseModel):
    text: str


@app.post("/api/agent/read-person")
def agent_read_person(body: ReadMe):
    """Gemini reads someone's own description of their situation, so the agents can shop for them."""
    if not body.text.strip():
        raise HTTPException(400, "Tell us a little about your situation.")
    try:
        return shopper.read_person(body.text)
    except gemini.LLMUnavailable as e:
        raise HTTPException(503, str(e))
    except Exception as e:
        from google.genai import errors as genai_errors
        if isinstance(e, genai_errors.APIError):
            raise HTTPException(502, f"Gemini refused the request ({e.code}): {e.message}")
        raise


class AgentConfirm(BaseModel):
    persona: str = "maya"
    offer_id: str
    profile: list[str] | None = None


@app.post("/api/agent/confirm")
def agent_confirm(body: AgentConfirm):
    try:
        return shopper.confirm(body.persona, body.offer_id, body.profile)
    except KeyError:
        raise HTTPException(404, "Unknown option")


@app.get("/api/agent/personas")
def agent_personas():
    return {k: {f: v[f] for f in ("name", "about", "task")} for k, v in shopper.PERSONAS.items()}


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
    return JSONResponse(gate.check(body.issuer, body.product_type, body.applicant_profile))


app.mount("/static", StaticFiles(directory=STATIC), name="static")
