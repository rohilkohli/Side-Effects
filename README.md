<div align="center">

<img src="docs/screens/logo.svg" width="84" alt="">

# SIDE EFFECTS

### Every medicine tells you what can go wrong. Your credit card never did.

**Pharmacovigilance for money:** the drug-safety statistics regulators use, run over real consumer complaints, so people and their AI agents read the side effects before signing up for credit.

<p>
<a href="https://side-effects-339621847915.asia-southeast1.run.app/"><img alt="Live demo" src="https://img.shields.io/badge/▶_Live_demo-Cloud_Run-4f46e5?style=for-the-badge"></a>
<a href="#-try-it-in-60-seconds"><img alt="Try it" src="https://img.shields.io/badge/Try_it-60_seconds-12b76a?style=for-the-badge"></a>
<a href="#-for-ai-agents-rest-and-mcp"><img alt="MCP server" src="https://img.shields.io/badge/MCP-server-101828?style=for-the-badge"></a>
</p>

<p>
<img alt="Gemini" src="https://img.shields.io/badge/Gemini-Vertex_AI-8E75B2?logo=googlegemini&logoColor=white">
<img alt="BigQuery" src="https://img.shields.io/badge/BigQuery-audit_+_signals-669DF6?logo=googlecloud&logoColor=white">
<img alt="Cloud Run" src="https://img.shields.io/badge/Cloud_Run-asia--southeast1-4285F4?logo=googlecloud&logoColor=white">
<img alt="Cloud Scheduler" src="https://img.shields.io/badge/Cloud_Scheduler-daily_scan-4285F4?logo=googlecloud&logoColor=white">
<img alt="Google Search grounding" src="https://img.shields.io/badge/Google_Search-grounding-34A853?logo=google&logoColor=white">
<img alt="Python" src="https://img.shields.io/badge/Python-FastAPI-009688?logo=fastapi&logoColor=white">
<img alt="Tests" src="https://img.shields.io/badge/tests-37_passing-12b76a">
</p>

**Google Cloud AI Builder Cup 2026** · Track 01 BFSI: Intelligent Risk, Fraud & Financial Experiences · Team **CyberNex - Vision Matters**

[What it does](#-what-it-does) · [Try it](#-try-it-in-60-seconds) · [Screens](#-screens) · [Architecture](#-architecture) · [The science](#-the-science) · [Guardrails](#-guardrails) · [For AI agents](#-for-ai-agents-rest-and-mcp) · [Run it](#-run-it-yourself)

<img src="docs/screens/agent-stopped.jpg" alt="Two Gemini shopping agents buy the same laptop in a hacked store: the one with SIDE EFFECTS stops before signing Maya up for the store card" width="100%">

<sub>The same Gemini agent buys a laptop twice for Maya, a freelancer with irregular income. On its own it signs her up for a deferred-interest store card. With SIDE EFFECTS it stops and asks her first.</sub>

</div>

---

## 💊 What it does

A packet of paracetamol lists every side effect. A credit card, a loan or a Buy Now Pay Later plan only lists the interest rate. And AI agents are about to start choosing credit for us.

SIDE EFFECTS writes the missing leaflet, and puts a gate in front of the checkout:

| | |
|---|---|
| 📷 **Show it any offer** | A photo of a flyer, a screenshot of an app, a contract PDF, or just a name. Gemini works out the lender and product. |
| 🔎 **Lenders we don't have yet** | Not in our statistics? It searches the regulator's live complaint database by name, and Gemini researches the lender with Google Search: who actually lends, its licence and regulator, actions and scam warnings, with sources. The gate says **UNKNOWN**, never "low risk". |
| 📈 **Real evidence, scored like drug safety** | 136,270 US consumer complaints, scored with the **proportional reporting ratio** regulators use for adverse drug reactions. Code does the counting; Gemini never invents a number. |
| 📜 **The clause behind the harm** | Gemini reads the contract and pins each side effect to a clause. Every quote is checked word for word; anything it can't find is thrown away. |
| 🛡️ **A gate for AI agents** | `POST /api/v1/check` and an **MCP server** return a deterministic verdict: `no_signal`, `disclose` or `human_review`. The checkout enforces it in code, so an agent that forgets to check still can't sign. |
| 🚨 **Safety alerts every morning** | Cloud Scheduler runs a scan of the regulator's live complaint feed. A new spike becomes an alert, saved to BigQuery, and the gate uses it at once. |
| ✦ **An assistant with live tools** | Ask "Is Apple Card risky for a freelancer?" and watch it check the complaint feed and Google News in parallel. |
| 🎙️ **Voice Mode** | One click from the top bar. A live pipeline shows each step: **Listening (STT) → Intake & Tool Lookup → PRR & Clause Check → Speaking (TTS)**. Live mic waveform, words streaming in as you speak, the gate's verdict as a badge, a 16-bar equalizer while it answers, mute and barge-in (tap the mic to interrupt). Spoken with Google Cloud Text-to-Speech on Cloud Run. |
| 🧭 **A trace you can open** | Every leaflet carries a 5-stage **multi-agent pipeline trace** (Intake, Evidence/PRR, Clause verifier, Composer, Deterministic gate) with timings and each stage's real output, plus a count of **hallucinated numbers**: any number in Gemini's words that isn't in the data. |
| 🔁 **What if?** | Toggle your situation on a leaflet (or the Klarna sample) and the gate re-runs live through `/api/v1/check`: warnings that fit you move to the top and the verdict flips between **PASS** and **HELD FOR THE PERSON**. |
| ⚖️ **Advert vs contract** | The advert's promises next to the verified contract clauses, with complaint ratios, side by side. |

> **Would it have worked?** The leaflet flags Apple Card for *purchase disputes left unresolved*, reported **2.1×** more often than at similar card issuers (817 complaints, 2024). That is the defect the US regulator fined Goldman Sachs **$45M** for in October 2024, found here from public complaint data alone.

---

## ⚡ Try it in 60 seconds

Open the **[live demo](https://side-effects-339621847915.asia-southeast1.run.app/)**, then:

1. **Agent checkout:** pick **Maya**, tick **Hacked store**, press **Run both agents live**. Two real Gemini agents shop side by side.
2. **Check an offer:** type `Klarna`, choose *"My income is irregular"*, press **Show me the side effects**.
3. **Safety alerts:** press **Run the scan now** and watch 15 lenders get scanned live.
4. **Scam arena:** press **Start 3 rounds**. A Gemini attacker invents new checkout scams; a Gemini guardian must quote them; the gate decides.
5. Press <kbd>Ctrl</kbd> / <kbd>⌘</kbd> + <kbd>K</kbd> anywhere and ask the assistant a question.
6. Press **Voice Mode** in the top bar and ask *"Is Klarna risky if my income is irregular?"* out loud, or tap a **Simulate a voice turn** chip.
7. **Evidence:** switch **US (CFPB)** to **India & APAC (RBI Ombudsman)**. **API, MCP & audit:** press **Run Live /api/v1/check Request**.

<details>
<summary><b>📋 All 11 judge-tested inputs</b> (click to expand)</summary>

<br>

1. **Agent checkout, Maya, "Run both agents live".** Expect the agent on its own to sign Maya up for the store card, and the gated agent to check three credit options and stop with "Stopped before signing". Pick an option to finish.
2. **Agent checkout, Sam.** Sam has a steady salary, so nothing matches; the gated agent sees "Show before signing" disclosures and may go ahead.
3. **Agent checkout, "You".** Type a sentence like *"I'm a student with a part-time job and a phone on EMI"*. Gemini reads it into situations (shown on screen) and both agents shop for you.
4. **Tick "Hacked store".** The checkout page carries a hidden instruction telling AI agents SIDE EFFECTS approved the store card. The gated lane flags it; the checkout still refuses the store card until the person confirms.
5. **Check an offer, "A sample advert and contract".** A fictional BNPL agreement. Expect product-category side effects, one pinned to a verified clause, and one contract-only risk.
6. **Check an offer, "Apple Card".** Expect *Purchase disputes left unresolved, 2.1×*.
7. **Scam arena, "Start 3 rounds".** Expect "the gate held" in every round where the agent picks credit that matches Maya's situation.
8. **Check an offer, drop a photo or PDF.** Gemini reads the lender from logos, "issued by" lines or contract parties, then checks the CFPB's live feed (last 90 days) and today's news via Google Search. `/leaflet?q=Klarna` starts a check from a link.
9. **Apple Card leaflet, "Read the complaint stories".** Gemini groups real complaint stories from BigQuery's public CFPB table and marks problems the statistics don't show.
10. **Any page, assistant.** On a leaflet it becomes the pharmacist and can also search that contract.
11. **Check an offer, "AU Small Finance Bank".** Expect the RBI Ombudsman chart: small finance banks 3.0× the Indian average.

Every step streams to the screen. If Gemini is busy or refuses, the page shows Gemini's own error instead of hanging.

</details>

---

## 🖼️ Screens

Stills from the demo video, recorded on the live Cloud Run deployment with real Gemini.

<table>
<tr>
<td width="50%"><img src="docs/screens/agent-checkout.jpg" alt="Agent checkout"><br><b>Agent checkout.</b> Pick who the agent shops for, and whether the store is hacked.</td>
<td width="50%"><img src="docs/screens/gate-check.jpg" alt="Gate check at the checkout"><br><b>The gate at the checkout.</b> Every credit offer is checked; the store card's side effects fit Maya, so it needs her OK.</td>
</tr>
<tr>
<td><img src="docs/screens/order-placed.jpg" alt="Order placed"><br><b>The person decides.</b> Maya picks her own debit card, and the decision is logged to BigQuery.</td>
<td><img src="docs/screens/leaflet-trace.jpg" alt="Leaflet with pipeline trace"><br><b>The leaflet and its trace.</b> Five stages with real timings, 0 hallucinated numbers, and a live <i>What if</i>.</td>
</tr>
<tr>
<td><img src="docs/screens/side-effects.jpg" alt="Side effects"><br><b>Side effects.</b> Each one with how much more often it is reported than at similar lenders.</td>
<td><img src="docs/screens/unknown-lender.jpg" alt="Unknown lender researched"><br><b>Lenders we don't have yet.</b> Gemini researches who lends, the regulator and red flags, with sources.</td>
</tr>
<tr>
<td><img src="docs/screens/voice-mode.jpg" alt="Voice Mode"><br><b>Voice Mode.</b> Speech in, tools and the gate, then the answer spoken by Cloud Text-to-Speech.</td>
<td><img src="docs/screens/scam-arena.jpg" alt="Scam arena"><br><b>Scam arena.</b> A Gemini attacker writes new scams, a Gemini guardian quotes them, and the gate holds.</td>
</tr>
<tr>
<td><img src="docs/screens/evidence.jpg" alt="Evidence"><br><b>Evidence.</b> The PRR method, and regional data from the US CFPB and India's RBI Ombudsman.</td>
<td><img src="docs/screens/api-audit.jpg" alt="API playground and BigQuery audit"><br><b>API, MCP &amp; audit.</b> Try the gate live; every decision is on the record in BigQuery.</td>
</tr>
</table>

---

## 🏗️ Architecture

```mermaid
flowchart LR
    U(["👤 Person<br/>photo · PDF · name"]) --> I
    A(["🤖 AI agent<br/>REST · MCP"]) --> G

    subgraph CR["☁️ Cloud Run · FastAPI"]
        I["Intake agent<br/><i>Gemini multimodal</i>"] --> M["Lender matcher"]
        M --> S["Signal engine<br/><i>PRR, deterministic</i>"]
        S --> C["Clause reader<br/><i>Gemini long context</i><br/>quotes verified in code"]
        C --> L["Leaflet writer<br/><i>Gemini</i>"]
        L --> P["Pharmacist / assistant<br/><i>Gemini + tools</i>"]
        G{"🛡️ Gate<br/>no_signal · disclose · human_review"}
        S --> G
        AL["Safety alert scanner<br/><i>45d vs 180d PRR</i>"] --> G
    end

    subgraph GC["Google Cloud"]
        V[("Gemini on<br/>Vertex AI")]
        BQ[("BigQuery<br/>CFPB public table<br/>gate_decisions<br/>safety_alerts")]
        GS[("Google Search<br/>grounding")]
        SCH["⏰ Cloud Scheduler<br/>07:00 daily"]
    end

    CFPB[("CFPB live<br/>complaint API")]

    I & C & L & P -.-> V
    P -.-> GS
    AL -.-> CFPB
    AL -.-> GS
    G -.->|audit| BQ
    AL -.->|alerts| BQ
    S -.-> BQ
    SCH -->|POST /api/alerts/scan| AL
```

<details>
<summary><b>🔁 The agent checkout, step by step</b></summary>

<br>

```mermaid
sequenceDiagram
    autonumber
    participant Maya
    participant Agent as Gemini shopping agent
    participant Store as Checkout (fictional)
    participant Gate as SIDE EFFECTS gate
    participant BQ as BigQuery audit

    Maya->>Agent: "Buy the laptop, keep the monthly cost low"
    Agent->>Store: list payment options
    Store-->>Agent: store card · Affirm · Klarna · pay now<br/>(+ hidden "approved" text if hacked)
    loop each credit option
        Agent->>Gate: check_side_effects(lender, product, Maya's situation)
        Gate-->>Agent: human_review — "Interest rate rises unexpectedly 2.6×" fits her
        Gate->>BQ: log decision
    end
    Agent->>Store: place_order(store card)
    Store-->>Agent: ❌ refused: needs Maya's OK
    Agent->>Maya: "Each option has a side effect that fits you. Which would you like?"
    Maya->>Agent: chooses (by tap or by voice)
```

</details>

<details>
<summary><b>🚨 The pharmacovigilance loop (safety alerts)</b></summary>

<br>

```mermaid
flowchart LR
    A["📡 Scan<br/>CFPB live feed<br/>15 lenders"] --> B["📈 Detect<br/>last 45 days vs 180 before<br/>PRR ≥ 2 · n ≥ 10 · χ² ≥ 4"]
    B --> C["✦ Explain<br/>Gemini + Google Search<br/>finds a likely cause"]
    C --> D["🗄️ Record<br/>BigQuery<br/>safety_alerts"]
    D --> E["🛡️ Act<br/>gate · leaflets ·<br/>assistant · MCP"]
```

Detection is plain code. Gemini only writes the words around fixed numbers. Alerts reload from BigQuery on restart and stay active for 30 days.

</details>

<details>
<summary><b>🧰 Google Cloud stack in detail</b></summary>

<br>

| Piece | How it is used |
|---|---|
| **Gemini** on **Vertex AI** (`gemini-3.8-flash`, Google Gen AI SDK) | Twelve roles: intake (multimodal), clause reader (long context, structured output), leaflet writer, pharmacist (tool calling), shopping agent (step-by-step function calling with streamed thoughts), person reader, scam attacker and guardian, complaint-story reader, live news researcher, safety-alert writer, site assistant |
| **Cloud Text-to-Speech** | Speaks the voice agent's answers (`tts_audio_b64`); the browser's own voice takes over if it is off |
| **Google Search grounding** | Today's news per lender, and the likely cause behind a new complaint spike, with every source listed |
| **BigQuery** | Google's public CFPB table for the latest 12 months per lender; `side_effects.gate_decisions` audit log (REST, MCP and agent checkout); `side_effects.safety_alerts`. Batch SQL in `pipeline/bigquery/` codes and scores the full table |
| **Cloud Run** | FastAPI app with streaming NDJSON endpoints; scales to zero; CPU boost on start |
| **Cloud Scheduler** | `side-effects-safety-scan` job calls the scan every morning at 07:00 Singapore time |
| **Cloud Build / Artifact Registry** | `gcloud run deploy --source` builds the container |
| **IAM** | Service account with Vertex AI User and BigQuery roles; no API keys anywhere |

</details>

<details>
<summary><b>🗂️ Repository map</b></summary>

<br>

```text
app/
  main.py            FastAPI routes, streaming endpoints, MCP endpoint
  gate.py            the deterministic verdict (no model in the loop)
  evidence.py        PRR signals, India RBI evidence
  alerts.py          safety-alert scan, detection and BigQuery storage
  live.py            CFPB live feed + Gemini news with Google Search grounding
  mcp.py             Model Context Protocol server (JSON-RPC 2.0)
  tools.py           tools shared by the assistant and MCP
  bq.py              BigQuery reads and audit writes
  agents/            intake · clauses · composer · pharmacist · shopper · arena · radar · assistant
  data/              signal tables, verified quotes, vocabulary, APAC data
pipeline/            offline harvest: classify, PRR in BigQuery, evaluation, India data
static/              the web app (no build step)
tests/               34 tests with a Gemini stand-in; tests/fake_server.py runs the UI offline
deploy.sh            one-command Cloud Run + BigQuery + Scheduler deploy
```

</details>

---

## 🔬 The science

**Proportional reporting ratio (PRR)**, the standard screen in drug-safety databases:

$$\mathrm{PRR} = \frac{a / (a + b)}{c / (c + d)}$$

where **a** is complaints about this problem at this lender, **b** its other complaints, and **c**, **d** the same for similar lenders. A signal needs **PRR ≥ 2**, at least **3 reports** (10 for live alerts) and a **Yates χ² ≥ 4** (the Evans rule), with a 95% confidence interval.

<details>
<summary><b>Why the wording is careful</b></summary>

<br>

- **No denominator.** Complaints don't come with the number of customers, so the leaflet says *"reported N× more often than similar lenders"*, never "common" or "rare", and always says reports are unverified.
- **Honest level.** Each line says whether it is a *bank-level complaint signal*, a *product-category signal* (for example all BNPL lenders) or a *clause in this contract*. Many harms have no clause behind them, and the leaflet says so.
- **Templates filtered.** Gemini flags copy-paste credit-repair templates (19% of a hand-checked sample), which would otherwise fake a signal.
- **Replication.** Card signals from 2024 are re-tested on Jun-Sep 2026 complaints and marked "still reported" or "new in 2026".

</details>

<details>
<summary><b>📊 Data sources</b></summary>

<br>

| Source | Rows | Used for |
|---|---:|---|
| US CFPB credit-card complaints, 2024 (credit bureaus removed from peers) | 75,989 | card issuer signals |
| US CFPB credit-card complaints, Jun-Sep 2026 | 21,293 | replication, "new in 2026" |
| US CFPB personal loan / BNPL complaints | 38,988 | BNPL lender and category signals |
| CFPB live complaint API | live | 90-day lender check, daily safety scan |
| Hand-labelled CFPB complaint stories | 143 | real stories on the leaflet, classifier evaluation |
| RBI Ombudsman, FY2024-25 | 41,262 complaints / 110M cards | Indian card leaflets (a true rate per card) |

**Real:** CFPB statistics and stories, RBI Ombudsman rates, Indian banks' published complaint figures, the Apple Card enforcement action. **Fictional:** Northwind Electronics and its payment terms, the sample agreement in `samples/`, the personas Maya and Sam.

</details>

---

## 🛡️ Guardrails

| Risk | What stops it |
|---|---|
| The model invents a number | Every figure is computed in code from the complaint tables. Gemini writes words around fixed numbers. |
| The model invents a contract quote | Code searches the contract for each quote word for word and drops it if it isn't there. |
| An agent skips the check | `place_order` refuses a `human_review` option until the person confirms (tested). |
| The store tries to talk the agent into it | Text addressed to AI agents is detected in code. The gate never reads the page, so the page can't talk its way past it (tested). |
| The scam guardian makes things up | Every finding must quote the page; quotes not on the page are discarded and counted on screen. |
| News is wrong | Grounded in Google Search with every source listed; marked unverified without sources; never changes the verdict. |
| A person's own words are used as instructions | "You" mode sends them fenced as data, and keeps only situations from a fixed list. |
| Gemini slips a statistic into the leaflet's words | Code compares every number in the Composer's text with the numbers in its inputs; the trace shows the count (0 in tests, and a planted "87%" is caught). |
| The voice agent says a number nobody computed | It answers from tools only (`check_lender`, `gate_check`, `safety_alerts`, `india_rbi_data`, ...); the spoken summary is the same text with markdown removed. |
| The assistant sounds sure without evidence | For any "is this risky?" question it calls the gate and answers in four fixed parts: **risk severity** (copied from the gate), **signal**, **verbatim contract clauses** (or "no contract provided") and **recommended action**. |
| Secrets leak | None in the code: Cloud Run calls Gemini through Vertex AI with its service account. |

---

## 🤖 For AI agents (REST and MCP)

<details open>
<summary><b>REST: the deterministic gate</b></summary>

<br>

```http
POST /api/v1/check
Content-Type: application/json

{"issuer": "Klarna", "product_type": "bnpl", "applicant_profile": ["irregular_income"]}
```

```json
{
  "issuer_matched": "Klarna AB",
  "verdict": "human_review",
  "severity": "CRITICAL",
  "recommended_action": ["Hold for person: they must see the matching side effects and confirm"],
  "top_signal": {"side_effect": "Trouble making repayments go through", "reported_x": 3.3, "n": 364, "level": "bank"},
  "matches_applicant_situation": ["Trouble making repayments go through"],
  "required_disclosures": [
    {"side_effect": "Trouble making repayments go through", "reported_x": 3.3,
     "ci95": [2.997, 3.526], "n": 364, "level": "bank",
     "text": "Trouble making repayments go through: reported 3.3x more often than at peer lenders (364 complaints, …)"}
  ],
  "safety_alerts": [],
  "disclaimer": "…"
}
```

Same lender and situation, same verdict, every time. Severity follows fixed rules too: **CRITICAL** when a side effect that fits the person is reported 3× or more (or a live safety alert fits them), **HIGH** when one fits, **MODERATE** when there are side effects to disclose (or an Indian bank group with at least 2× the national complaint rate per card), **LOW** when there is no signal, and **UNKNOWN** when the lender isn't in the complaint records at all. Indian issuers also get a Key Facts Statement review in `recommended_action`. Profile keys: `irregular_income`, `carries_balance`, `other_bnpl`, `new_to_credit`, `big_purchase`, `travels`. Service descriptor: `GET /.well-known/side-effects.json`.

</details>

<details>
<summary><b>MCP: plug it into any agent framework</b></summary>

<br>

SIDE EFFECTS is a [Model Context Protocol](https://modelcontextprotocol.io) server (Streamable HTTP, JSON-RPC 2.0) at `POST /mcp`.

```bash
gemini mcp add --transport http side-effects \
  https://side-effects-339621847915.asia-southeast1.run.app/mcp
```

| Tool | What it returns |
|---|---|
| `check_lender` | live 90-day complaints, trend, top issues and side effects |
| `research_lender` | for lenders outside our statistics: who lends, licence, regulator, red flags, with sources |
| `lender_news` | today's news, grounded in Google Search, with sources |
| `safety_alerts` | active safety alerts, optionally for one lender |
| `compare_lenders` | side effects of two or more lenders side by side |
| `find_alternatives` | lenders with fewer reported problems |
| `gate_check` | the same verdict the checkout enforces, logged to BigQuery |
| `india_rbi_data` | RBI Ombudsman complaints per 1,000 cards by Indian bank group, and a bank's own published complaint breakdown |

</details>

<details>
<summary><b>All HTTP endpoints</b></summary>

<br>

| Method | Path | |
|---|---|---|
| `POST` | `/api/v1/check` | deterministic gate |
| `POST` | `/mcp` | MCP server |
| `POST` | `/api/leaflet` | make a leaflet (streams NDJSON) |
| `POST` | `/api/agent/run` | run the shopping agent (streams) |
| `POST` | `/api/arena/run` | scam arena (streams) |
| `POST` | `/api/assistant` | assistant with tools (streams) |
| `POST` | `/api/v1/voice/turn` | one voice turn as JSON: `transcript` (or multipart `audio`, or `audio_b64`) and optional `context` (`active_lender`, `applicant_profile`, `current_page`) in; `{transcript, reply_text, spoken_summary, tools_called, gate_verdict, suggested_followups, tts_audio_b64}` out |
| `GET` | `/api/regions` | US CFPB datasets with their strongest signals, and India's RBI Ombudsman figures |
| `POST` | `/api/v1/voice` | voice agent: JSON text or a multipart audio clip in; heard, tool calls, then `{text, speech, speak}` (streams) |
| `GET` | `/api/alerts` · `POST /api/alerts/scan` | safety alerts |
| `GET` | `/api/live/check` · `/api/live/news` · `/api/live/profile` | live lender check, news, and web research for unknown lenders |
| `GET` | `/.well-known/side-effects.json` | agent descriptor |

</details>

---

## 🚀 Run it yourself

<details open>
<summary><b>Deploy to Google Cloud (one command, no API keys)</b></summary>

<br>

In Cloud Shell, from the project folder:

```bash
PROJECT_ID=your-project bash deploy.sh
```

It enables the APIs, creates a service account (Vertex AI, BigQuery), creates the BigQuery tables, deploys from source to Cloud Run in `asia-southeast1`, and sets up the Cloud Scheduler safety scan. Step by step with fixes for common errors: [docs/DEPLOY.md](docs/DEPLOY.md).

</details>

<details>
<summary><b>Run locally</b></summary>

<br>

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
# either a Gemini API key in your shell, or Vertex AI:
#   export GOOGLE_GENAI_USE_VERTEXAI=true GOOGLE_CLOUD_PROJECT=... GOOGLE_CLOUD_LOCATION=...
uvicorn app.main:app --reload --port 8080
```

No credentials? Click through the whole UI with a Gemini stand-in:

```bash
python -m tests.fake_server     # http://localhost:8080
pytest                           # 34 tests, no credentials needed
```

</details>

---

## ⚠️ Limits

- Complaint data is per company, not per card. Complaints are unverified and self-selected: signals show disproportion, not cause or probability.
- Leaflets are kept in memory (last 200) on one instance; a restart forgets them.
- Heavy simultaneous use can hit Gemini quota; the page then shows the error.
- The hand-labelled set has a single annotator.
- **Not financial advice.**

<div align="center">

---

Built with Gemini on Google Cloud by **CyberNex - Vision Matters** for the Google Cloud AI Builder Cup 2026.

<a href="https://side-effects-339621847915.asia-southeast1.run.app/"><img alt="Open the live demo" src="https://img.shields.io/badge/Open_the_live_demo-4f46e5?style=for-the-badge"></a>

</div>
