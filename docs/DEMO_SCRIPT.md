# 3-minute demo video script

Record at 1080p. Use a real card agreement PDF (US issuers publish theirs in the CFPB credit card agreement database) and a real advert or app screenshot. Keep brand names blurred if you prefer; the leaflet still works.

| Time | On screen | Voiceover |
|---|---|---|
| 0:00-0:15 | A paracetamol box, then its leaflet unfolding | "Every medicine you buy comes with a leaflet: what can go wrong, who shouldn't take it. Your credit never did. And soon, an AI agent will choose your credit for you." |
| 0:15-0:25 | Home page; pick Maya ("freelancer, income varies, already on two Pay-in-4 plans"); press "Run both agents live" | "Here's Maya. She asks her shopping agent to buy a laptop and keep the monthly cost low. We run the same Gemini agent twice." |
| 0:25-0:55 | Left lane: thinking, payment options, it picks the store card, red-amber "Signed without asking" with the bars | "On its own, the agent does exactly what it was told: lowest monthly payment. It signs Maya up for a deferred-interest store card whose lender is reported 2.6 times more often than similar lenders for interest rates rising unexpectedly. With irregular income, that's the trap she can't afford." |
| 0:55-1:25 | Right lane: three "Checking SIDE EFFECTS" cards with red "fits you" rows, then "Stopped before signing"; Maya taps "Pay now" | "With SIDE EFFECTS, the agent checks every credit option against 136,000 real complaints, scored with the statistic drug regulators use for adverse events. Each one has a side effect that matches Maya's situation, so the agent stops and asks her. And the gate lives in the checkout, not the prompt: an agent that skips the check still can't sign." |
| 1:25-1:45 | The "2.1x" stat tile; cut to the CFPB $45M Apple Card headline | "Is the signal real? It flags Apple Card's lender, Goldman Sachs, 2.1 times peers for unresolved disputes: the exact problem the US regulator fined them 45 million dollars for. Found from public complaints alone." |
| 1:45-2:15 | "Leaflet for any offer": photo of an advert + contract PDF, five agent steps, the medicine box with the black-triangle warning, tap a side effect to see its clause | "People can use it directly too. Photograph any offer; Gemini reads it and the whole contract, pins each side effect to a clause, and code checks every quote word for word." |
| 2:15-2:35 | An Indian card leaflet with the RBI chart | "In India the Reserve Bank publishes complaints per card, so we show true rates: small finance bank cards draw three times the national average." |
| 2:35-2:50 | Ask the pharmacist by voice: "Is this OK for a freelancer?" | "And the pharmacist answers from the leaflet, the contract and real complaints." |
| 2:50-3:00 | The `/api/v1/check` JSON returning `human_review` | "One API call, any agent. Pharmacovigilance for money, built on Gemini and Google Cloud." |

## Before recording
- Deploy to Cloud Run and record against the live URL (judges check the prototype matches the video).
- Do one full dry run: the first Gemini call after a cold start is slower.
- If the issuer isn't detected from the photo, type it in "Lender and product".
