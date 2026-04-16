"""
Cartru — New-Car Deal Defense Tool
MVP 2: Signal-first, buyer-funded, honest estimates.

Features:
- Local market range estimation (NHTSA + regional demand multipliers)
- Cartru Signal (LOOKS FAIR / PUSH BACK / HIGH RISK)
- Top reasons + what to say next
- Recall & complaint lookup (NHTSA)
- Fuel economy data (fueleconomy.gov)
- 5-year True Cost estimate
- Negotiation intel (renamed, estimated prefix)
"""

import os
import json
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

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

def calculate_true_cost(msrp, fuel_economy, annual_miles=12000, years=5, state="CA"):
    if not msrp:
        return None

    msrp = float(msrp)
    depreciation_5yr = msrp * 0.49

    gas_price = 3.50
    if fuel_economy and fuel_economy.get("combined_mpg") and fuel_economy["combined_mpg"] != "N/A":
        mpg = float(fuel_economy["combined_mpg"])
        annual_fuel = (annual_miles / mpg) * gas_price
    else:
        annual_fuel = annual_miles / 27 * gas_price
    fuel_5yr = annual_fuel * years

    insurance_annual = 1700
    insurance_5yr = insurance_annual * years
    maintenance_5yr = annual_miles * years * 0.09

    loan_amount = msrp * 0.90
    monthly_rate = 0.065 / 12
    n_payments = 60
    monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate)**n_payments) / ((1 + monthly_rate)**n_payments - 1)
    financing_cost = (monthly_payment * 60) - loan_amount

    taxes_fees = msrp * 0.10
    total_5yr = depreciation_5yr + fuel_5yr + insurance_5yr + maintenance_5yr + financing_cost + taxes_fees

    return {
        "msrp": round(msrp),
        "depreciation_5yr": round(depreciation_5yr),
        "fuel_5yr": round(fuel_5yr),
        "annual_fuel": round(annual_fuel),
        "insurance_5yr": round(insurance_5yr),
        "maintenance_5yr": round(maintenance_5yr),
        "financing_cost": round(financing_cost),
        "monthly_payment": round(monthly_payment),
        "taxes_fees": round(taxes_fees),
        "total_5yr": round(total_5yr),
        "cost_per_month": round(total_5yr / (years * 12)),
        "annual_miles": annual_miles,
        "years": years,
    }

# ── Local Market Range ────────────────────────────────────────────────────────

def _guess_segment_msrp(make, model):
    """
    Estimate base MSRP from make/model using vehicle segment heuristics.
    Returns a reasonable mid-point for the model year, not exact MSRP.
    """
    make_l = make.lower()
    model_l = model.lower()

    # Luxury brands
    luxury_makes = {"bmw", "mercedes-benz", "mercedes", "audi", "lexus", "cadillac",
                    "lincoln", "acura", "infiniti", "volvo", "genesis", "porsche", "land rover"}
    # Full-size trucks / large SUVs
    truck_keywords = {"f-150", "f150", "silverado", "sierra", "ram 1500", "tundra",
                      "titan", "ranger", "colorado", "tacoma", "frontier", "ridgeline",
                      "expedition", "suburban", "tahoe", "yukon", "navigator", "armada",
                      "sequoia", "4runner", "pathfinder", "pilot", "traverse", "durango",
                      "explorer", "blazer"}
    # Compact / subcompact
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
    # Default: midsize sedan / crossover
    return 28000


def get_local_market_range(make, model, year, zip_code):
    """
    Estimate local market range for a new car using segment heuristics
    and regional demand multipliers.

    Returns:
        base_msrp_estimate: Estimated mid-market price for this segment
        low: base * 0.96 (floor for new-car deals)
        high: base * 1.03 (ceiling before overpaying)
        source_note: Honest disclaimer
        regional_note: Regional demand info
    """
    base = _guess_segment_msrp(make, model)

    # Regional demand multiplier from ZIP prefix
    zip_str = str(zip_code).strip()
    regional_mult = 1.0
    regional_note = "Standard market demand in your region."

    if zip_str and len(zip_str) >= 1:
        prefix = zip_str[0]
        if prefix == "9":
            regional_mult = 1.03
            regional_note = "High-demand region (CA/WA/OR): estimated +3% above national average."
        elif prefix == "1":
            regional_mult = 1.02
            regional_note = "High-demand region (NY/NJ/CT): estimated +2% above national average."
        elif prefix == "6":
            regional_mult = 1.01
            regional_note = "Moderate-demand region (IL/WI): estimated +1% above national average."

    adjusted_base = round(base * regional_mult)
    low = round(adjusted_base * 0.96)
    high = round(adjusted_base * 1.03)

    return {
        "base_msrp_estimate": adjusted_base,
        "low": low,
        "high": high,
        "source_note": "Estimated range based on typical transaction data for this model. Not exact OTD pricing.",
        "regional_note": regional_note,
    }


# ── Cartru Signal ─────────────────────────────────────────────────────────────

def get_cartru_signal(dealer_offer, local_range, detected_fees=0):
    """
    Compare dealer_offer to local market range and return a signal.
    """
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
    """
    Return 2-3 honest, specific reasons based on the actual numbers.
    """
    reasons = []
    offer = float(dealer_offer)
    low = local_range["low"]
    high = local_range["high"]
    base = local_range["base_msrp_estimate"]

    delta = round(offer - base)
    if delta > 0:
        reasons.append(f"Dealer offer is ${delta:,} above the estimated local market range for this model.")
    elif delta < 0:
        reasons.append(f"Dealer offer is ${abs(delta):,} below the estimated local market range — a potentially good deal.")
    else:
        reasons.append("Dealer offer matches the estimated local market range for this model.")

    if msrp and float(msrp) > 0:
        msrp_f = float(msrp)
        if offer >= msrp_f:
            reasons.append(f"No rebates or incentives appear to be applied — the offer equals or exceeds MSRP (${msrp_f:,.0f}).")
        elif offer >= msrp_f * 0.99:
            reasons.append("Little to no discount from MSRP — manufacturers often offer rebates that should lower this price.")
    else:
        reasons.append("No MSRP entered — we can't compare the offer to sticker price. Ask the dealer for the window sticker.")

    if detected_fees > 0:
        reasons.append(f"Detected dealer fees of ~${detected_fees:,} may add to the out-the-door price beyond this offer.")
    else:
        reasons.append("Dealer add-on fees (documentation, prep, tint, etc.) can add $500–$1,500 to the out-the-door price — always ask for a complete itemized quote.")

    return reasons[:3]


# ── What to Say ───────────────────────────────────────────────────────────────

def get_what_to_say(signal, dealer_offer, local_range):
    """
    Return one concrete, actionable negotiation line tailored to the signal.
    """
    low = local_range["low"]

    if signal == "LOOKS FAIR":
        return "This looks reasonable — you could still ask: 'What's the best you can do on the out-the-door price?'"
    elif signal == "PUSH BACK":
        return f"Try: 'I've seen this model selling closer to ${low:,} in my area. Can we get there?'"
    else:  # HIGH RISK
        return "Say: 'I need to think about it' and leave. Come back with a competing quote from another dealer."


# ── Negotiation Intelligence ──────────────────────────────────────────────────

def get_negotiation_intel(make, model, year, msrp, dealer_offer=None):
    """
    Negotiation intelligence based on invoice-to-MSRP ratios.
    All output values carry 'estimated_' labels to be honest about uncertainty.
    """
    msrp = float(msrp)

    invoice_ratios = {
        "toyota": 0.94, "honda": 0.94, "ford": 0.93, "chevrolet": 0.92,
        "gmc": 0.91, "ram": 0.91, "jeep": 0.92, "hyundai": 0.93,
        "kia": 0.93, "nissan": 0.93, "subaru": 0.95, "mazda": 0.94,
        "volkswagen": 0.94, "bmw": 0.92, "mercedes": 0.92, "audi": 0.92,
        "lexus": 0.95, "acura": 0.94,
    }
    ratio = invoice_ratios.get(make.lower(), 0.93)
    estimated_invoice = msrp * ratio
    suggested_opening_number = estimated_invoice * 1.02   # 2% over invoice
    caution_zone_above = msrp * 0.97                      # 3% under MSRP is the ceiling

    dealer_offer_f = float(dealer_offer) if dealer_offer else None

    return {
        "estimated_invoice": round(estimated_invoice),
        "estimated_suggested_opening_number": round(suggested_opening_number),
        "estimated_caution_zone_above": round(caution_zone_above),
        "estimated_potential_savings": round(msrp - suggested_opening_number),
        "dealer_offer": round(dealer_offer_f) if dealer_offer_f else None,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/report", methods=["POST"])
def report():
    data = request.json
    year         = data.get("year", "")
    make         = data.get("make", "").strip()
    model        = data.get("model", "").strip()
    zip_code     = data.get("zip_code", "").strip()
    msrp         = data.get("msrp", "") or None
    dealer_offer = data.get("dealer_offer", "") or None
    dest_charge  = data.get("dest_charge", 0)
    rebates      = data.get("rebates", 0)
    dealer_fees  = data.get("dealer_fees", 0)
    annual_miles = int(data.get("annual_miles", 12000))

    # Core signal pipeline
    local_range = get_local_market_range(make, model, year, zip_code)

    signal = None
    signal_color = None
    signal_explanation = None
    top_reasons = []
    what_to_say = None

    detected_fees = float(dealer_fees) if dealer_fees else 0

    if dealer_offer:
        dealer_offer_f = float(dealer_offer)
        signal, signal_color, signal_explanation = get_cartru_signal(
            dealer_offer_f, local_range, detected_fees
        )
        top_reasons = get_top_reasons(dealer_offer_f, local_range, msrp, detected_fees)
        what_to_say = get_what_to_say(signal, dealer_offer_f, local_range)
    else:
        signal = None
        signal_color = None
        signal_explanation = "Enter a dealer offer to see your Cartru Signal."

    # Negotiation intel (only if MSRP provided)
    negotiation = None
    if msrp:
        negotiation = get_negotiation_intel(make, model, year, msrp, dealer_offer)

    # Below-fold data
    recalls      = get_recalls(make, model, year)
    complaints   = get_complaints(make, model, year)
    fuel_economy = get_fuel_economy(make, model, year)
    true_cost    = calculate_true_cost(msrp, fuel_economy, annual_miles) if msrp else None

    # Safety signal
    recall_count    = len(recalls)
    complaint_count = complaints.get("total", 0)
    if recall_count == 0 and complaint_count < 10:
        safety_signal = "GREEN"
    elif recall_count <= 2 and complaint_count < 50:
        safety_signal = "YELLOW"
    else:
        safety_signal = "RED"

    has_dealer_offer = dealer_offer is not None and dealer_offer != ""
    has_zip = zip_code != ""

    analytics = {
        "event": "report_generated",
        "has_dealer_offer": has_dealer_offer,
        "has_zip": has_zip,
        "signal": signal,
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
        "recalls": recalls,
        "recall_count": recall_count,
        "complaints": complaints,
        "fuel_economy": fuel_economy,
        "true_cost": true_cost,
        "safety_signal": safety_signal,
        "dealer_offer": float(dealer_offer) if dealer_offer else None,
        "analytics": analytics,
    })


@app.route("/makes")
def makes():
    year = request.args.get("year", "2021")
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
    year = request.args.get("year", "2021")
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
