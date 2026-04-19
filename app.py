"""
Cartru — New-Car Deal Defense Tool
MVP 2.2.2: Scenario Engine — live financial calculator pass.

Features:
- Local market range estimation
- Cartru Signal (LOOKS FAIR / PUSH BACK / HIGH RISK)
- Top reasons + what to say next
- Junk fee analysis
- Term Trap Detector (proper amortization, 4-term comparison)
- Negotiation script generator
- Printable summary
- Recall & complaint lookup (NHTSA)
- Fuel economy data (fueleconomy.gov)
- Dynamic N-Year True Cost estimate (loan-term driven)
- Tip jar endpoint
"""

import os
import json
import logging
import requests
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── NHTSA APIs ────────────────────────────────────────────────────────────────

def get_recalls(make, model, year):
    try:
        url = f"https://api.nhtsa.gov/recalls/recallsByVehicle?make={make}&model={model}&modelYear={year}"
        r = requests.get(url, timeout=10)
        data = r.json()
        recalls = data.get("results", [])
        return [{
            "id": rec.get("NHTSAActionNumber", ""),
            "component": rec.get("Component", "Unknown"),
            "summary": rec.get("Summary", "")[:200],
            "consequence": rec.get("Consequence", ""),
            "remedy": rec.get("Remedy", ""),
            "reportDate": rec.get("ReportReceivedDate", "")
        } for rec in recalls]
    except Exception:
        return []


def get_complaints(make, model, year):
    try:
        url = f"https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}"
        r = requests.get(url, timeout=10)
        data = r.json()
        complaints = data.get("results", [])
        components = {}
        for c in complaints:
            comp = c.get("components", "Unknown")
            components[comp] = components.get(comp, 0) + 1
        return {
            "total": data.get("Count", 0),
            "by_component": dict(sorted(components.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    except Exception:
        return {"total": 0, "by_component": {}}


# ── Fuel Economy API ──────────────────────────────────────────────────────────

def get_fuel_economy(make, model, year):
    try:
        url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?year={year}&make={make}&model={model}"
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        data = r.json()
        items = data.get("menuItem", [])
        if isinstance(items, dict):
            items = [items]
        if not items:
            return None

        vehicle_id = items[0].get("value")
        if not vehicle_id:
            return None

        url2 = f"https://www.fueleconomy.gov/ws/rest/vehicle/{vehicle_id}"
        r2 = requests.get(url2, headers={"Accept": "application/json"}, timeout=10)
        v = r2.json()

        return {
            "city_mpg": v.get("city08", "N/A"),
            "highway_mpg": v.get("highway08", "N/A"),
            "combined_mpg": v.get("comb08", "N/A"),
            "fuel_type": v.get("fuelType", "Gasoline"),
            "engine": v.get("displ", ""),
            "cylinders": v.get("cylinders", ""),
            "transmission": v.get("trany", ""),
            "annual_fuel_cost": v.get("fuelCost08", "N/A"),
        }
    except Exception:
        return None


# ── True Cost Calculator ──────────────────────────────────────────────────────

def calculate_true_cost(msrp, fuel_economy, annual_miles=13500, years=None,
                        gas_price=3.45, apr=0.068, loan_term_months=72):
    """
    Calculate true cost of ownership over the loan term.
    All calculations are driven by loan_term_months, not a hardcoded 5 years.
    """
    if not msrp:
        return None

    msrp = float(msrp)
    years_of_loan = loan_term_months / 12
    if years is None:
        years = years_of_loan

    # Depreciation over loan term (49% is typical 5yr; scale proportionally, cap at 70%)
    depreciation_rate = 0.49 * (years / 5.0)
    depreciation = round(msrp * min(depreciation_rate, 0.70))

    # Fuel cost
    if fuel_economy and fuel_economy.get("combined_mpg") and fuel_economy["combined_mpg"] != "N/A":
        combined_mpg = float(fuel_economy["combined_mpg"])
    else:
        combined_mpg = 27.0

    fuel_cost = (annual_miles / combined_mpg) * gas_price * years
    annual_fuel_cost = fuel_cost / years
    monthly_fuel_cost = annual_fuel_cost / 12

    # Insurance (unchanged: $1,700/yr)
    insurance = 1700 * years
    monthly_insurance = 1700 / 12  # ~$141.67

    # Maintenance ($0.09/mile)
    maintenance = annual_miles * years * 0.09
    monthly_maintenance = (annual_miles * 0.09) / 12

    # Financing cost — proper amortization
    principal = msrp * 0.90  # assume 10% down
    monthly_rate = apr / 12
    n = int(loan_term_months)

    if monthly_rate > 0:
        monthly_payment = principal * (monthly_rate * (1 + monthly_rate) ** n) / ((1 + monthly_rate) ** n - 1)
    else:
        monthly_payment = principal / n

    total_interest = (monthly_payment * n) - principal

    # Taxes & fees (10% of MSRP)
    taxes_fees = msrp * 0.10

    # Total cost
    total_cost = depreciation + fuel_cost + insurance + maintenance + total_interest + taxes_fees

    # Monthly budget
    total_monthly_budget = monthly_payment + monthly_fuel_cost + monthly_insurance + monthly_maintenance

    return {
        "msrp": round(msrp),
        # Ownership components
        "depreciation": depreciation,
        "fuel_cost": round(fuel_cost),
        "annual_fuel_cost": round(annual_fuel_cost),
        "monthly_fuel_cost": round(monthly_fuel_cost),
        "insurance": round(insurance),
        "monthly_insurance": round(monthly_insurance),
        "maintenance": round(maintenance),
        "monthly_maintenance": round(monthly_maintenance),
        "total_interest": round(total_interest),
        "financing_cost": round(total_interest),
        "monthly_payment": round(monthly_payment),
        "taxes_fees": round(taxes_fees),
        "total_cost": round(total_cost),
        # Term info
        "years_of_loan": years_of_loan,
        "loan_term_months": loan_term_months,
        "annual_miles": annual_miles,
        "years": years,
        "gas_price": gas_price,
        "apr": apr,
        "combined_mpg": combined_mpg,
        # Monthly budget
        "total_monthly_budget": round(total_monthly_budget),
        # Legacy field names (backward compat)
        "depreciation_5yr": depreciation,
        "fuel_5yr": round(fuel_cost),
        "annual_fuel": round(annual_fuel_cost),
        "insurance_5yr": round(insurance),
        "maintenance_5yr": round(maintenance),
        "total_5yr": round(total_cost),
        "cost_per_month": round(total_cost / (years * 12)),
    }


# ── Term Comparison ───────────────────────────────────────────────────────────

def calculate_term_comparison(dealer_price, apr, terms=None):
    """
    Compare monthly payment, total interest, and total cost across 4 loan terms.
    Returns a dict with 'terms' list and 'baseline_term' = 60.
    """
    if terms is None:
        terms = [48, 60, 72, 84]

    dealer_price = float(dealer_price)
    principal = dealer_price * 0.90  # assume 10% down
    monthly_rate = apr / 12

    results = []
    baseline_interest = None

    for term in terms:
        if monthly_rate > 0:
            mp = principal * (monthly_rate * (1 + monthly_rate) ** term) / ((1 + monthly_rate) ** term - 1)
        else:
            mp = principal / term

        total_interest = (mp * term) - principal
        total_cost = dealer_price + total_interest

        entry = {
            "term": term,
            "monthly_payment": round(mp),
            "total_interest": round(total_interest),
            "total_cost": round(total_cost),
            "extra_interest": 0,
            "extra_months": 0,
        }
        results.append(entry)

        if term == 60:
            baseline_interest = round(total_interest)

    # vs. 60-month baseline
    for item in results:
        if item["term"] == 60:
            item["extra_interest"] = 0
            item["extra_months"] = 0
        else:
            item["extra_interest"] = item["total_interest"] - (baseline_interest or 0)
            item["extra_months"] = item["term"] - 60

    return {
        "terms": results,
        "baseline_term": 60,
        "baseline_interest": baseline_interest,
    }


# ── Local Market Range ────────────────────────────────────────────────────────

def _guess_segment_msrp(make, model):
    make_l = make.lower()
    model_l = model.lower()

    luxury_makes = {"bmw", "mercedes-benz", "mercedes", "audi", "lexus", "cadillac",
                    "lincoln", "acura", "infiniti", "volvo", "genesis", "porsche", "land rover"}
    truck_keywords = {"f-150", "f150", "silverado", "sierra", "ram 1500", "tundra",
                      "titan", "ranger", "colorado", "tacoma", "frontier", "ridgeline",
                      "expedition", "suburban", "tahoe", "yukon", "navigator", "armada",
                      "sequoia", "4runner", "pathfinder", "pilot", "traverse", "durango",
                      "explorer", "blazer"}
    compact_keywords = {"civic", "corolla", "elantra", "forte", "sentra", "jetta",
                        "golf", "impreza", "focus", "cruze", "spark", "fit", "yaris",
                        "accent", "rio", "mirage", "versa", "maverick", "bronco sport",
                        "venue", "trax", "encore", "renegade", "compass", "hrv", "crv",
                        "rav4", "tucson", "sportage", "escape", "equinox", "tiguan"}

    if make_l in luxury_makes:
        return 55000
    for kw in truck_keywords:
        if kw in model_l:
            return 45000
    for kw in compact_keywords:
        if kw in model_l:
            return 23000
    return 28000


def get_local_market_range(make, model, year, zip_code):
    base = _guess_segment_msrp(make, model)

    zip_str = str(zip_code).strip()
    regional_mult = 1.0
    regional_note = "National average demand."
    area_label = "National"

    if zip_str and len(zip_str) >= 1:
        prefix = zip_str[0]
        if prefix == "9":
            regional_mult = 1.03
            regional_note = "High-demand region (CA/WA/OR): estimated +3% above national average."
            area_label = "West Coast"
        elif prefix == "1":
            regional_mult = 1.02
            regional_note = "High-demand region (NY/NJ/CT): estimated +2% above national average."
            area_label = "Northeast"
        elif prefix == "6":
            regional_mult = 1.01
            regional_note = "Moderate-demand region (IL/WI): estimated +1% above national average."
            area_label = "Midwest"
        elif zip_str:
            area_label = f"ZIP {zip_str[:3]}xx area"

    adjusted_base = round(base * regional_mult)
    low = round(adjusted_base * 0.96)
    high = round(adjusted_base * 1.03)

    return {
        "base_msrp_estimate": adjusted_base,
        "low": low,
        "high": high,
        "area_label": area_label,
        "source_note": "Estimated range based on typical transaction data for this segment. Not exact OTD pricing.",
        "regional_note": regional_note,
    }


# ── Cartru Signal ─────────────────────────────────────────────────────────────

def get_cartru_signal(dealer_offer, local_range, detected_fees=0):
    offer = float(dealer_offer)
    low = local_range["low"]
    high = local_range["high"]

    disclaimer = "Signal is based on estimated local market data, not a guarantee. Actual prices vary by trim, options, and local availability."

    if offer <= low:
        return (
            "LOOKS FAIR",
            "green",
            "This offer is at or below the typical range for this vehicle in your area. " + disclaimer
        )
    elif offer <= high:
        return (
            "PUSH BACK",
            "yellow",
            "This offer is within range but there's likely room to negotiate. " + disclaimer
        )
    else:
        return (
            "HIGH RISK",
            "red",
            "This offer is above the typical range. Don't sign without negotiating. " + disclaimer
        )


# ── Top Reasons ───────────────────────────────────────────────────────────────

def get_top_reasons(dealer_offer, local_range, msrp=None, detected_fees=0):
    reasons = []
    offer = float(dealer_offer)
    low = local_range["low"]
    high = local_range["high"]
    base = local_range["base_msrp_estimate"]

    delta = round(offer - base)
    if delta > 0:
        reasons.append(f"Dealer offer is ${delta:,} above the estimated local market range for this model.")
    elif delta < 0:
        reasons.append(f"Dealer offer is ${abs(delta):,} below the estimated local market range — potentially a good deal.")
    else:
        reasons.append("Dealer offer matches the estimated local market range for this model.")

    if msrp and float(msrp) > 0:
        msrp_f = float(msrp)
        if offer >= msrp_f:
            reasons.append(f"No discount from MSRP — the offer equals or exceeds sticker price (${msrp_f:,.0f}). Manufacturers often offer rebates.")
        elif offer >= msrp_f * 0.99:
            reasons.append(f"Less than 1% off MSRP (${msrp_f:,.0f}). Rebates and incentives could lower this price further.")
        else:
            discount_pct = round((1 - offer / msrp_f) * 100, 1)
            reasons.append(f"Offer is {discount_pct}% below MSRP (${msrp_f:,.0f}). Check if additional factory rebates apply.")
    else:
        reasons.append("No MSRP entered — ask the dealer for the window sticker and compare to this offer.")

    if detected_fees > 500:
        reasons.append(f"Dealer fees of ${detected_fees:,.0f} are higher than typical ($100–$500). Negotiate or ask for itemization.")
    else:
        reasons.append("Dealer add-on fees can add $500–$1,500 to the out-the-door price — always ask for a complete itemized quote.")

    return reasons[:3]


# ── What to Say ───────────────────────────────────────────────────────────────

def get_what_to_say(signal, dealer_offer, local_range):
    low = local_range["low"]

    if signal == "LOOKS FAIR":
        return "This looks reasonable — but still ask: 'What's the best you can do on the out-the-door price including all fees?'"
    elif signal == "PUSH BACK":
        return f"Try: 'I've seen this model selling closer to ${low:,} in my area. Can we get there on the out-the-door price?'"
    else:
        return "Say 'I need to think about it' and leave. Come back with a competing quote from another dealer — that's your leverage."


# ── Negotiation Intel ─────────────────────────────────────────────────────────

def get_negotiation_intel(make, model, year, msrp, dealer_offer=None):
    msrp = float(msrp)

    invoice_ratios = {
        "toyota": 0.94, "honda": 0.94, "ford": 0.93, "chevrolet": 0.92,
        "gmc": 0.91, "ram": 0.91, "jeep": 0.92, "hyundai": 0.93,
        "kia": 0.93, "nissan": 0.93, "subaru": 0.95, "mazda": 0.94,
        "volkswagen": 0.94, "bmw": 0.92, "mercedes": 0.92, "audi": 0.92,
        "lexus": 0.95, "acura": 0.94, "tesla": 1.0, "dodge": 0.91,
    }
    ratio = invoice_ratios.get(make.lower(), 0.93)
    estimated_invoice = msrp * ratio
    suggested_opening_number = estimated_invoice * 1.02
    caution_zone_above = msrp * 0.97

    dealer_offer_f = float(dealer_offer) if dealer_offer else None

    return {
        "estimated_invoice": round(estimated_invoice),
        "estimated_suggested_opening_number": round(suggested_opening_number),
        "estimated_caution_zone_above": round(caution_zone_above),
        "estimated_potential_savings": round(msrp - suggested_opening_number),
        "dealer_offer": round(dealer_offer_f) if dealer_offer_f else None,
    }


# ── Junk Fee Analysis ─────────────────────────────────────────────────────────

def get_junk_fee_analysis(dealer_fees, destination_charge, add_ons):
    dealer_fees_f = float(dealer_fees) if dealer_fees else 0
    dest_charge_f = float(destination_charge) if destination_charge else 0

    # Doc fee analysis
    if dealer_fees_f == 0:
        doc_fee_note = "No doc fee entered. Ask for the exact doc fee — typical range is $100–$500."
        doc_fee_flag = "unknown"
    elif dealer_fees_f <= 300:
        doc_fee_note = f"Doc fee of ${dealer_fees_f:,.0f} is reasonable (typical: $100–$500)."
        doc_fee_flag = "ok"
    elif dealer_fees_f <= 500:
        doc_fee_note = f"Doc fee of ${dealer_fees_f:,.0f} is on the high end but within the typical range."
        doc_fee_flag = "caution"
    else:
        doc_fee_note = f"Doc fee of ${dealer_fees_f:,.0f} is above the typical $100–$500 range. Push back or ask for a reduction."
        doc_fee_flag = "high"

    # Destination charge analysis
    if dest_charge_f == 0:
        dest_note = "No destination charge entered. Factory destination fee is typically $900–$1,800 — it's non-negotiable but should be on the window sticker."
        dest_flag = "unknown"
    elif dest_charge_f <= 1800:
        dest_note = f"Destination charge of ${dest_charge_f:,.0f} is within the normal factory range ($900–$1,800). This is set by the manufacturer, not the dealer."
        dest_flag = "ok"
    else:
        dest_note = f"Destination charge of ${dest_charge_f:,.0f} exceeds the typical factory range of $900–$1,800. Ask why it's higher."
        dest_flag = "high"

    junk_addons = [
        {"name": "Nitrogen tire fill", "cost": "$150–$300", "verdict": "Skip it", "note": "Air is 78% nitrogen already. A complete waste of money."},
        {"name": "Paint protection / clear coat sealant", "cost": "$300–$800", "verdict": "Skip it", "note": "Modern cars have good factory paint. Buy your own wax for $20."},
        {"name": "Window tint", "cost": "$200–$600", "verdict": "Get it elsewhere", "note": "Shop window tint locally for 50–70% less than dealer price."},
        {"name": "VIN etching / theft deterrent", "cost": "$200–$400", "verdict": "Skip it", "note": "Has no proven theft deterrence. Pure profit for dealers."},
        {"name": "Fabric / leather protection", "cost": "$200–$500", "verdict": "Skip it", "note": "Buy a $25 can of Scotchgard. Dealer product is the same thing."},
        {"name": "Extended warranty at signing", "cost": "$1,000–$3,000", "verdict": "Wait", "note": "Never buy an extended warranty at signing. You can always buy later, often cheaper, after the factory warranty expires."},
        {"name": "GAP insurance at dealer", "cost": "$400–$900", "verdict": "Buy elsewhere", "note": "Your own auto insurer sells GAP coverage for $20–$40/year. Don't buy it from the F&I office."},
        {"name": "Credit life / disability insurance", "cost": "varies", "verdict": "Skip it", "note": "Overpriced junk product. You don't need it."},
    ]

    add_ons_lower = (add_ons or "").lower()
    flagged_addons = []
    if any(kw in add_ons_lower for kw in ["nitrogen", "nitro"]):
        flagged_addons.append("Nitrogen tire fill")
    if any(kw in add_ons_lower for kw in ["paint", "clear coat", "sealant"]):
        flagged_addons.append("Paint protection")
    if any(kw in add_ons_lower for kw in ["tint", "window"]):
        flagged_addons.append("Window tint")
    if any(kw in add_ons_lower for kw in ["vin", "etch"]):
        flagged_addons.append("VIN etching")
    if any(kw in add_ons_lower for kw in ["fabric", "leather", "protection"]):
        flagged_addons.append("Fabric/leather protection")
    if any(kw in add_ons_lower for kw in ["warranty", "extended"]):
        flagged_addons.append("Extended warranty")
    if any(kw in add_ons_lower for kw in ["gap"]):
        flagged_addons.append("GAP insurance")

    total_fees = round(dealer_fees_f + dest_charge_f)

    flags = sum([1 for f in [doc_fee_flag, dest_flag] if f in ("high", "caution")])
    flags += len(flagged_addons)

    if flags == 0 and dealer_fees_f <= 300 and dest_charge_f <= 1500:
        fee_verdict = "Reasonable"
        verdict_color = "green"
    elif flags <= 1 or (dealer_fees_f <= 500 and dest_charge_f <= 1800):
        fee_verdict = "Review Carefully"
        verdict_color = "yellow"
    else:
        fee_verdict = "High — Push Back"
        verdict_color = "red"

    return {
        "dealer_doc_fee": dealer_fees_f,
        "doc_fee_note": doc_fee_note,
        "doc_fee_flag": doc_fee_flag,
        "destination_charge": dest_charge_f,
        "dest_note": dest_note,
        "dest_flag": dest_flag,
        "junk_addons_to_watch": junk_addons,
        "flagged_from_input": flagged_addons,
        "total_known_fees": total_fees,
        "fee_verdict": fee_verdict,
        "verdict_color": verdict_color,
    }


# ── Negotiation Script ────────────────────────────────────────────────────────

def get_negotiation_script(signal, dealer_offer, local_range, make, model):
    offer = float(dealer_offer) if dealer_offer else 0
    low = local_range["low"]
    high = local_range["high"]
    base = local_range["base_msrp_estimate"]
    vehicle = f"{make} {model}"

    if signal == "LOOKS FAIR":
        opening = f"'I've done my research on {vehicle} pricing and your number looks close to market. I'm ready to buy today if we can get the out-the-door price — including all fees and add-ons — down to ${int(offer * 0.98):,}.'"
    elif signal == "PUSH BACK":
        opening = f"'I've been tracking {vehicle} prices in my area and the market range I'm seeing is ${low:,}–${base:,}. I want to buy today — can we start the conversation at ${low:,} on the vehicle price, before fees?'"
    else:
        opening = f"'I appreciate your time, but the numbers I've seen on the {vehicle} in my area are significantly lower — around ${low:,}–${base:,}. At ${offer:,.0f} I'm not able to move forward. What's the best you can actually do on the vehicle price?'"

    if signal in ("PUSH BACK", "HIGH RISK"):
        counter = f"'I understand you need to make a profit — I respect that. But I've got quotes from two other dealers and I've done the research. I can do ${int(low * 1.01):,} out the door, today, and we're done. Can you make that work?'"
    else:
        counter = f"'I'm close, but I need you to meet me at ${int(offer * 0.97):,} out the door. I'm ready to sign today. Can your manager do that?'"

    walk_away = "'I really appreciate your time — you've been helpful. But I'm not there yet on the numbers. I'm going to check with a couple other dealers. If you can sharpen the pencil to ${:,}, call me and I'll come back today.'.".format(int(low * 1.005))

    email = (
        f"Subject: Quote Request — {make} {model}\n\n"
        f"Hi,\n\n"
        f"I'm actively looking to purchase a new {make} {model} and comparing offers from multiple dealers in my area.\n\n"
        f"I'm looking for your best out-the-door price (vehicle price + destination + all dealer fees, before taxes/registration). "
        f"I'm not interested in payment-based quotes — just the total purchase price.\n\n"
        f"I plan to make a decision within the next few days. Please send your best number and I'll get back to you quickly.\n\n"
        f"Thank you,\n[Your name]\n[Your phone number]"
    )

    return {
        "opening_line": opening,
        "counter_line": counter,
        "walk_away_line": walk_away,
        "email_template": email,
        "pro_tip": "Visit or call competing dealers on the same day. Dealers respond faster when they know you're shopping actively."
    }


# ── Printable Summary ─────────────────────────────────────────────────────────

def get_printable_summary(vehicle, signal, local_range, dealer_offer, negotiation, top_reasons):
    year = vehicle.get("year", "")
    make = vehicle.get("make", "")
    model = vehicle.get("model", "")
    area = local_range.get("area_label", "National")
    low = local_range["low"]
    high = local_range["high"]
    offer = dealer_offer or 0

    lines = [
        "=" * 52,
        f"  CARTRU DEAL ANALYSIS",
        f"  {year} {make} {model}",
        f"  Generated: {datetime.now().strftime('%B %d, %Y')}",
        "=" * 52,
        "",
        f"CARTRU SIGNAL: {signal or 'N/A'}",
        "",
        f"LOCAL MARKET RANGE ({area}): ${low:,} – ${high:,}",
        f"DEALER OFFER: ${float(offer):,.0f}" if offer else "DEALER OFFER: Not entered",
        "",
        "TOP REASONS:",
    ]

    for i, reason in enumerate(top_reasons or [], 1):
        lines.append(f"  {i}. {reason}")

    lines += ["", "-" * 52, ""]

    if negotiation:
        lines += [
            "NEGOTIATION INTEL (Estimated):",
            f"  Est. Invoice Price: ${negotiation.get('estimated_invoice', 0):,}",
            f"  Suggested Opening: ${negotiation.get('estimated_suggested_opening_number', 0):,}",
            f"  Potential Savings vs MSRP: ${negotiation.get('estimated_potential_savings', 0):,}",
            "",
        ]

    lines += [
        "-" * 52,
        "",
        "DISCLAIMER: All estimates are based on segment data",
        "and regional market signals. Not a guarantee of price.",
        "Use this as a starting point for your negotiation.",
        "",
        "cartru.com — buyer-funded, no dealer leads, no ads.",
        "=" * 52,
    ]

    return "\n".join(lines)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/report", methods=["POST"])
def report():  # noqa: C901
    try:
        return _report_inner()
    except Exception as e:
        logger.error(f"Report endpoint error: {e}", exc_info=True)
        return jsonify({"error": "Analysis failed — please try again.", "detail": str(e)}), 500

def _report_inner():
    data = request.json
    year               = data.get("year", "")
    make               = data.get("make", "").strip()
    model              = data.get("model", "").strip()
    zip_code           = data.get("zip_code", "").strip()
    msrp               = data.get("msrp", "") or None
    dealer_offer       = data.get("dealer_offer", "") or None
    destination_charge = data.get("destination_charge", 0)
    dealer_fees        = data.get("dealer_fees", 0)
    add_ons            = data.get("add_ons", "")
    monthly_payment    = data.get("monthly_payment", "") or None

    # New scenario engine params
    apr           = float(data.get("apr", 0.068))
    loan_term     = int(data.get("loan_term", 72))
    gas_price     = float(data.get("gas_price", 3.45))
    annual_miles  = int(data.get("annual_miles", 13500))

    # Core signal pipeline
    local_range = get_local_market_range(make, model, year, zip_code)

    signal = None
    signal_color = None
    signal_explanation = None
    top_reasons = []
    what_to_say = None
    detected_fees = float(dealer_fees) if dealer_fees else 0

    # If dealer_offer not provided, estimate at 95% of MSRP
    dealer_price_is_estimated = False
    if dealer_offer:
        dealer_price = float(dealer_offer)
    elif msrp:
        dealer_price = float(msrp) * 0.95
        dealer_offer = dealer_price
        dealer_price_is_estimated = True
    else:
        dealer_price = local_range["base_msrp_estimate"] * 0.95
        dealer_offer = dealer_price
        dealer_price_is_estimated = True

    dealer_offer_f = float(dealer_price)
    signal, signal_color, signal_explanation = get_cartru_signal(
        dealer_offer_f, local_range, detected_fees
    )
    top_reasons = get_top_reasons(dealer_offer_f, local_range, msrp, detected_fees)
    what_to_say = get_what_to_say(signal, dealer_offer_f, local_range)

    # Negotiation intel
    negotiation = None
    if msrp:
        negotiation = get_negotiation_intel(make, model, year, msrp, dealer_offer_f)

    # Junk fee analysis
    junk_fees = get_junk_fee_analysis(dealer_fees, destination_charge, add_ons)

    # Negotiation script
    negotiation_script = None
    if signal:
        negotiation_script = get_negotiation_script(signal, dealer_offer_f, local_range, make, model)

    # Recall & complaint data
    recalls    = get_recalls(make, model, year)
    complaints = get_complaints(make, model, year)

    # Fuel economy
    fuel_economy = get_fuel_economy(make, model, year)

    # True cost (dynamic, driven by loan_term)
    true_cost = None
    if msrp:
        true_cost = calculate_true_cost(
            msrp, fuel_economy,
            annual_miles=annual_miles,
            gas_price=gas_price,
            apr=apr,
            loan_term_months=loan_term
        )

    # Term comparison
    term_comparison = calculate_term_comparison(dealer_price, apr)

    # Printable summary
    printable_summary = get_printable_summary(
        {"year": year, "make": make, "model": model},
        signal, local_range, dealer_offer_f, negotiation, top_reasons
    )

    # Safety signal
    recall_count    = len(recalls)
    complaint_count = complaints.get("total", 0)
    if recall_count == 0 and complaint_count < 10:
        safety_signal = "GREEN"
    elif recall_count <= 2 and complaint_count < 50:
        safety_signal = "YELLOW"
    else:
        safety_signal = "RED"

    # OTD estimate
    dest_f  = float(destination_charge) if destination_charge else 0
    fees_f  = float(dealer_fees) if dealer_fees else 0
    est_taxes       = round(dealer_offer_f * 0.08)
    est_registration = 350
    otd_estimate = round(dealer_offer_f + dest_f + fees_f + est_taxes + est_registration)

    # Years of loan
    years_of_loan = loan_term / 12

    analytics = {
        "event": "report_generated",
        "has_dealer_offer": not dealer_price_is_estimated,
        "dealer_price_is_estimated": dealer_price_is_estimated,
        "has_zip": zip_code != "",
        "signal": signal,
        "make": make,
        "model": model,
        "year": year,
        "apr": apr,
        "loan_term": loan_term,
        "gas_price": gas_price,
        "annual_miles": annual_miles,
    }

    return jsonify({
        "vehicle": {"year": year, "make": make, "model": model},
        "zip_code": zip_code,
        "local_range": local_range,
        "signal": signal,
        "signal_color": signal_color,
        "signal_explanation": signal_explanation,
        "top_reasons": top_reasons,
        "what_to_say": what_to_say,
        "negotiation": negotiation,
        "junk_fees": junk_fees,
        "payment_trap": None,  # deprecated — replaced by term_comparison
        "negotiation_script": negotiation_script,
        "printable_summary": printable_summary,
        "recalls": recalls,
        "recall_count": recall_count,
        "complaints": complaints,
        "fuel_economy": fuel_economy,
        "true_cost": true_cost,
        "safety_signal": safety_signal,
        "otd_estimate": otd_estimate,
        "dealer_offer": dealer_offer_f,
        "dealer_price_is_estimated": dealer_price_is_estimated,
        "destination_charge": dest_f,
        "dealer_fees": fees_f,
        "term_comparison": term_comparison,
        "years_of_loan": years_of_loan,
        "loan_term": loan_term,
        "apr": apr,
        "gas_price": gas_price,
        "annual_miles": annual_miles,
        "analytics": analytics,
    })


@app.route("/models-for-brand")
def models_for_brand():
    """Return list of model names for a given make and year from fueleconomy.gov."""
    make = request.args.get("make", "").strip()
    year = request.args.get("year", "2025").strip()

    if not make:
        return jsonify({"error": "make is required"}), 400

    try:
        r = requests.get(
            f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?year={year}&make={make}",
            headers={"Accept": "application/json"},
            timeout=10
        )
        data = r.json()
        items = data.get("menuItem", [])
        if isinstance(items, dict):
            items = [items]
        models = sorted(set(item["value"] for item in items if item.get("value")))
        return jsonify({"make": make, "year": year, "models": models})
    except Exception as e:
        logger.error(f"models-for-brand error: {e}")
        return jsonify({"make": make, "year": year, "models": []})


@app.route("/grouped-models")
def grouped_models():
    """Return model strings grouped into families for a given make and year."""
    make = request.args.get("make", "").strip()
    year = request.args.get("year", "2025").strip()

    if not make:
        return jsonify({"error": "make is required"}), 400

    try:
        r = requests.get(
            f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?year={year}&make={make}",
            headers={"Accept": "application/json"},
            timeout=10
        )
        data = r.json()
        items = data.get("menuItem", [])
        if isinstance(items, dict):
            items = [items]

        all_models = sorted(set(item["value"] for item in items if item.get("value")))

        # Group by family: extract first word(s) as the family name
        # Strategy: group by longest common prefix that ends at a space
        from collections import defaultdict
        families = defaultdict(list)

        for model in all_models:
            parts = model.split()
            first = parts[0]
            # BMW-style pure numeric prefix (e.g. "330i", "540i") → group by series number
            if first[0].isdigit() and any(c.isdigit() for c in first):
                # Extract leading digits for series grouping (330i → "3 Series", 540i → "5 Series")
                leading = ''.join(c for c in first if c.isdigit())
                if len(leading) >= 3:
                    series_num = leading[0]  # First digit = series (3xx → 3 Series)
                    family = f"{series_num} Series"
                else:
                    family = first
            else:
                # Use first word as family (handles RAV4, GR86, 4Runner correctly)
                family = first

            families[family].append(model)

        # Sort families, sort trims within each family
        grouped = [
            {"family": fam, "trims": sorted(trims)}
            for fam, trims in sorted(families.items())
        ]

        return jsonify({"make": make, "year": year, "grouped": grouped, "total": len(all_models)})

    except Exception as e:
        logger.error(f"grouped-models error: {e}")
        return jsonify({"make": make, "year": year, "grouped": [], "total": 0})


@app.route("/tip-jar", methods=["POST"])
def tip_jar():
    """Log tip intent and return thank-you response."""
    data = request.json or {}
    logger.info(f"TIP_JAR_CLICK | make={data.get('make', '')} model={data.get('model', '')} signal={data.get('signal', '')} ts={datetime.utcnow().isoformat()}")
    return jsonify({
        "status": "thank_you",
        "message": "Thank you for supporting independent car buying tools."
    })


# Legacy endpoints (keep for compatibility)
@app.route("/makes")
def makes():
    year = request.args.get("year", "2025")
    try:
        r = requests.get(
            f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/make?year={year}",
            headers={"Accept": "application/json"}, timeout=10
        )
        items = r.json().get("menuItem", [])
        return jsonify([i["value"] for i in items])
    except Exception:
        return jsonify([])


@app.route("/models")
def models():
    year = request.args.get("year", "2025")
    make = request.args.get("make", "")
    try:
        r = requests.get(
            f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?year={year}&make={make}",
            headers={"Accept": "application/json"}, timeout=10
        )
        items = r.json().get("menuItem", [])
        return jsonify([i["value"] for i in items])
    except Exception:
        return jsonify([])


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
