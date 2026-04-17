# Cartru Changelog

## mvp1-stable
**Deployed:** 2026-04-16
- TCO calculator (5-year true cost)
- Recall lookup via NHTSA API
- Fuel economy data via fueleconomy.gov
- Negotiation intel: estimated invoice, target offer, walk-away price
- Dealer playbook (5 tactics)
- Basic buy/negotiate/walk away verdict
- No ZIP-based market data; no paywall

**Rollback:** `git checkout mvp1-stable` then redeploy on Railway

---

## mvp2-new-car-deal-defense
**Deployed:** 2026-04-16
- Cartru Signal (LOOKS FAIR / PUSH BACK / HIGH RISK)
- ZIP-based local market range
- Simplified above-fold result hierarchy
- Deal Pass paywall ($19 mock) — removed in 2.1
- Language: Suggested Opening Number, Caution Zone, estimated ranges
- Collapsible below-fold sections

**Rollback:** `git checkout mvp2-new-car-deal-defense` then redeploy

---

## mvp2.1-paywall-removed (in progress)

**Strategic direction (from Maxime):**
- Remove paywall entirely — free is the better growth strategy at this stage
- No Canadian complexity, US-only, US ZIP codes only
- Move premium features into core free experience (don't delete value, redistribute it)
- Calculator energy: quick input, instant feedback, easy to tweak

**UX changes:**
- Remove Year from main flow (auto-detect or infer from model)
- ZIP optional and light ("Using your area — change")
- Brand logos instead of dropdowns
- Model cards instead of list
- Live result updates (calculator feel)
- Easy back-navigation without restarting
- Hide exotic brands (Ferrari, Lambo, etc.) — focus on negotiable brands
- US only (no Canada, no postal codes, no French)

**Features moved from paywall to free:**
- Full out-the-door breakdown
- Junk-fee / add-on review
- Payment-trap explanation
- Suggested opening number + caution zone
- Negotiation script
- Printable summary

**Result structure:**
- Top: Signal + range + offer delta + top 3 reasons + what to say
- Below: deeper analysis (OTD, fees, payment trap, negotiation script)

**Monetization:**
- Simple tip jar at bottom ("If this helped you save money...")
- Tips unlock nothing — pure support
- No Stripe integration needed initially (can use Buy Me a Coffee link or similar)

**Success criteria:**
- Feels like a live tool, not a form
- Fully free
- Premium features integrated cleanly
- Tip jar present
- More fun, more shareable, less friction
