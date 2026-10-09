# 3-minute demo video script

Record at 1080p. Use a real card agreement PDF (US issuers publish theirs in the CFPB credit card agreement database) and a real advert or app screenshot. Keep brand names blurred if you prefer; the leaflet still works.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00-0:15 | A paracetamol box, then its leaflet unfolding | "Every medicine you buy comes with a leaflet: what can go wrong, who shouldn't take it, what it interacts with. Your credit card never did." |
| 0:15-0:30 | A glossy "0% interest, pay later!" advert on a phone | "Finance has the raw material: millions of complaints. Nobody turns them into a warning you see at the moment you sign." |
| 0:30-0:45 | SIDE EFFECTS home page; take a photo of the advert, attach the contract PDF, tap "irregular income" | "SIDE EFFECTS does what drug regulators do. Show it the offer." |
| 0:45-1:10 | The five agent steps ticking through | "Gemini reads the advert and spots what it leaves out. We find the lender in 136,000 real complaints and run the same statistic regulators use for drug safety. Then Gemini reads every page of the contract to find the clause behind each problem, and code checks every quote word for word." |
| 1:10-1:45 | The leaflet. Tap "Purchase disputes left unresolved" (2.1x) to show the clause, then the real complaint stories | "This card's lender is reported 2.1 times more often than similar lenders for unresolved disputes. That signal is Goldman Sachs and the Apple Card: the US regulator fined them 45 million dollars for exactly this. Our method finds it from public complaints alone." |
| 1:45-2:05 | Scroll to "Before you sign" and "Consider a generic" | "Because I said my income is irregular, it tells me what to watch for, and which similar lenders don't show these problems." |
| 2:05-2:25 | An Indian card leaflet with the RBI chart | "In India the Reserve Bank publishes complaints per card, so we show true rates: small finance bank cards draw three times the national average." |
| 2:25-2:45 | Tap the pharmacist, ask by voice: "Is this OK for a freelancer?" | "And you can ask the pharmacist, who answers from the leaflet, the contract and real complaints." |
| 2:45-3:00 | The JSON check endpoint returning `human_review` | "Soon AI agents will sign people up for credit. Before they do, they can read the leaflet: SIDE EFFECTS returns a machine-readable verdict. Pharmacovigilance for money, built on Gemini and Google Cloud." |

## Before recording
- Deploy to Cloud Run and record against the live URL (judges check the prototype matches the video).
- Do one full dry run: the first Gemini call after a cold start is slower.
- If the issuer isn't detected from the photo, type it in "Lender and product".
