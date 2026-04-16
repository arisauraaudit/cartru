# Cartru Changelog

## mvp1-stable
**Deployed:** 2026-04-16
- TCO calculator (5-year true cost: depreciation, fuel, insurance, maintenance, financing, taxes)
- Recall lookup via NHTSA API
- Fuel economy data via fueleconomy.gov
- Negotiation intel: estimated invoice, target offer, walk-away price
- Dealer playbook (5 tactics)
- Basic buy/negotiate/walk away verdict
- No ZIP-based market data; no paywall

**Rollback:** `git checkout mvp1-stable` then redeploy on Railway

---

## mvp2-new-car-deal-defense (in progress)

**MVP 1 bugs being fixed in this sprint (from Maxime IC review):**
1. MSRP logic too fragile — user-entered MSRP must never drive verdict alone
2. Tone too certain — replace "Our Verdict/BUY" with "Cartru Signal/Looks Fair/Push Back/High Risk"
3. Report overloaded above fold — first screen = signal + local range + top 3 reasons + what to say
4. TCO/annual miles pushed below fold — secondary to deal judgment
5. No location awareness — ZIP-based local market range added (clearly labeled as estimate)
6. Negotiation anchor weak — tie to local market range + fees, not just MSRP math
7. Free/paid line blurry — free: signal+range+2-3 reasons+what to say | paid: full OTD, fee review, script
8. Meta-bug: tone more certain than logic — MVP2 reverses this

**New features:**
- New homepage: "Don't sign a bad new-car deal"
- ZIP-based local market price range (sampled listings, clearly labeled estimate)
- Simplified above-the-fold result hierarchy
- Language: Suggested Opening Number, Caution Zone, estimated ranges
- Deal Pass paywall ($19) with mock unlock state
- Analytics tracking (report generated, ZIP, signal, Deal Pass views/clicks)
