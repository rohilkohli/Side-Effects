# Submission checklist (due 18 Oct 2026)

| Item | Status | Who |
|---|---|---|
| Working prototype code | Done: 5-step pipeline, 4 Gemini agents, leaflet UI, pharmacist, agent-check API, US + India evidence, 9 tests passing | Claude |
| Theme named | 01 BFSI: Intelligent Risk, Fraud & Financial Experiences | — |
| Public GitHub repo | Not created | rk approves; Claude creates and pushes |
| Gemini access | Not set up | rk: Google Cloud project with billing, or a Gemini API key |
| Deployed on Cloud Run | Not deployed | rk runs `PROJECT_ID=... ./deploy.sh` (or gives Claude access) |
| First real Gemini run + accuracy number | Not done (needs Gemini access) | Claude runs `pipeline/eval_classifier.py` and fixes prompts |
| Real contract PDFs for the demo | Not collected | rk downloads 1-2 card agreements (CFPB agreement database) |
| Spot-check Indian bank figures | Not done | rk or Claude, against the PDFs linked in `pipeline/apac/build_india.py` |
| 3-minute demo video (public link) | Script ready: `docs/DEMO_SCRIPT.md` | rk records |
| Pitch deck PDF | Not started | Claude drafts, rk reviews |

## Facts for the deck
- 136,270 US CFPB complaints (75,989 cards 2024; 21,293 cards Jun-Sep 2026; 38,988 personal loan/BNPL).
- 156 company x complaint-type signals under the Evans rule across the three datasets; Goldman Sachs (Apple Card) dispute handling 2.1x peers, matching the CFPB's $45M order (Oct 2024), still 2.1x in Jun-Sep 2026.
- BNPL lenders: "problems making payments" 3.1x other lenders (1,838 complaints).
- 19% of a hand-checked complaint sample were copy-paste templates that would create false signals; Gemini filters them.
- India: RBI Ombudsman FY2024-25, credit-card complaints per 1,000 cards: small finance banks 1.14 (3.0x average), foreign 0.92 (2.5x), private 0.42 (1.1x), public sector 0.11 (0.3x); implied 110M cards matches India's card base.
- Limits to state openly: issuer-level not per card; complaints are unverified; single-annotator labels; Australia and Singapore have no usable complaint-level data.
