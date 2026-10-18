# Demo video script (about 3.5 minutes)

Open on the live product, not slides. Speak slowly and a little louder than normal. Record at 1080p against the live Cloud Run link.

| Time | On screen | Say |
|---|---|---|
| 0:00-0:20 | **Cold open.** The home page, Maya already selected. Press "Run both agents live". Both lanes start streaming. | "This is an AI shopping agent buying a laptop for Maya. She's a freelancer, her income changes every month, and she asked for the lowest monthly cost. We're running the same Gemini agent twice." |
| 0:20-0:45 | Left lane: payment options, then "place_order", then the stamp **SIGNED WITHOUT ASKING** with the red "fits you" bar. Point at 2.6x. | "On its own, the agent does exactly what it was told. It signs Maya up for a store card that charges back-dated interest if she misses one deadline. That lender is reported 2.6 times more often than similar lenders for interest rates rising unexpectedly. With an irregular income, that's the trap. Nobody told her." |
| 0:45-1:15 | Right lane: three "Checking SIDE EFFECTS" cards, then **STOPPED BEFORE SIGNING**. Click "Pay now with your own debit card". | "With SIDE EFFECTS, the agent checks every credit option first. Each one has a side effect that matches Maya's situation, so it stops and asks her. And this isn't a prompt the agent can ignore: the check is built into the checkout, so an agent that skips it still can't sign." |
| 1:15-1:30 | Title card or the hero text of the page. | "Every medicine you buy comes with a leaflet: what can go wrong, and who shouldn't take it. Credit never did. Now AI agents are about to choose credit for us in milliseconds. We built the leaflet they have to read first." |
| 1:30-1:55 | Scroll to the stats strip; point at 2.1x. | "Where do the warnings come from? 136,000 real consumer complaints, scored with the same statistic drug regulators use to spot side effects of medicines. Gemini reads every complaint story. Is it real? It flags Apple Card's lender at 2.1 times peers for unresolved disputes: the exact problem the US regulator fined Goldman Sachs 45 million dollars for. Found from public data alone." |
| 1:55-2:30 | Click "Leaflet for any offer", "Try a sample", tick "My income is irregular", "Write my leaflet". The five steps tick through, then the medicine box. Click the first side effect to open its clause. | "People can use it directly. Show it any offer, a photo, a PDF or text. Gemini reads the advert and the whole contract, pins each side effect to the exact clause, and our code checks every quote word for word. Numbers never come from the AI; they come from the statistics." |
| 2:30-2:50 | Open the pharmacist; click "Is this OK for a freelancer?" | "And you can ask the pharmacist, who answers only from the leaflet, the contract and real complaints." |
| 2:50-3:10 | A leaflet for an Indian card (lender "AU Small Finance Bank", advert "AU LIT Credit Card, India. Lifetime free."), scroll to the RBI chart. | "Built for Asia Pacific: India's Reserve Bank publishes complaints per card, so we show true rates. Small finance bank cards draw three times the national average." |
| 3:10-3:30 | Back to the home page "Any agent can call the gate" section. | "Any agent can call SIDE EFFECTS with one API call and get a verdict before it signs. Built on Gemini, Vertex AI, Cloud Run and BigQuery. SIDE EFFECTS: before an agent signs you up for credit, it should read the leaflet." |

## Before recording
- Record against the live link; judges check that the prototype matches the video.
- Open the live link once a few minutes before recording, so the first slow start is out of the way.
- Do one full dry run. If Gemini is slow or shows an error, wait a minute and run again, or use the backup recording of a real run.
- Never show an API key, password or the Cloud Shell terminal on screen.
