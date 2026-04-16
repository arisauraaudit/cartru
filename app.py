"""
Cartru / Dealer Antidote — Prototype v0.1
Buyer-side car intelligence. No dealer relationships. No conflicts.

Features:
- Recall lookup (NHTSA)
- Complaint lookup (NHTSA)
- Fuel economy data (fueleconomy.gov)
- 5-year True Cost estimate
- Simple web interface
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
    except Exception as e:
        return []

def get_complaints(make, model, year):
    try:
        url = f"https://api.nhtsa.gov/complaints/complaintsByVehicle?make={make}&model={model}&modelYear={year}"
        r = requests.get(url, timeout=10)
        data = r.json()
        complaints = data.get("results", [])
        # Group by component
        components = {}
        for c in complaints:
            comp = c.get("components", "Unknown")
            components[comp] = components.get(comp, 0) + 1
        return {
            "total": data.get("Count", 0),
            "by_component": dict(sorted(components.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    except:
        return {"total": 0, "by_component": {}}

# ── Fuel Economy API ──────────────────────────────────────────────────────────

def get_fuel_economy(make, model, year):
    try:
        # Get vehicle IDs
        url = f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/options?year={year}&make={make}&model={model}"
        r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
        data = r.json()
        items = data.get("menuItem", [])
        # API returns dict instead of list when only one result
        if isinstance(items, dict):
            items = [items]
        if not items:
            return None

        # Get first vehicle ID
        vehicle_id = items[0].get("value")
        if not vehicle_id:
            return None

        # Get fuel economy details
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
    except Exception as e:
        return None

# ── True Cost Calculator ──────────────────────────────────────────────────────

def calculate_true_cost(msrp, fuel_economy, annual_miles=12000, years=5, state="CA"):
    """
    Estimates 5-year true cost of ownership.
    All figures in USD.
    """
    if not msrp:
        return None

    msrp = float(msrp)

    # Depreciation (avg ~49% over 5 years for mainstream vehicles)
    depreciation_5yr = msrp * 0.49

    # Fuel cost (assume $3.50/gallon average)
    gas_price = 3.50
    if fuel_economy and fuel_economy.get("combined_mpg") and fuel_economy["combined_mpg"] != "N/A":
        mpg = float(fuel_economy["combined_mpg"])
        annual_fuel = (annual_miles / mpg) * gas_price
    else:
        annual_fuel = annual_miles / 27 * gas_price  # assume 27mpg average
    fuel_5yr = annual_fuel * years

    # Insurance (US average ~$1,700/year, varies by vehicle class)
    insurance_annual = 1700
    insurance_5yr = insurance_annual * years

    # Maintenance (avg $0.09/mile for mainstream vehicles)
    maintenance_5yr = annual_miles * years * 0.09

    # Financing cost (if financed — assume 10% down, 6.5% APR, 60 months)
    loan_amount = msrp * 0.90
    monthly_rate = 0.065 / 12
    n_payments = 60
    monthly_payment = loan_amount * (monthly_rate * (1 + monthly_rate)**n_payments) / ((1 + monthly_rate)**n_payments - 1)
    financing_cost = (monthly_payment * 60) - loan_amount

    # Taxes & fees (avg ~10% of MSRP)
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

# ── Negotiation Intelligence ──────────────────────────────────────────────────

def get_negotiation_intel(make, model, year, msrp, dealer_offer=None):
    """
    Basic negotiation intelligence based on known invoice-to-MSRP ratios.
    In a full version, this would pull real transaction data.
    """
    msrp = float(msrp)

    # Typical invoice prices are 92-97% of MSRP depending on brand
    invoice_ratios = {
        "toyota": 0.94, "honda": 0.94, "ford": 0.93, "chevrolet": 0.92,
        "gmc": 0.91, "ram": 0.91, "jeep": 0.92, "hyundai": 0.93,
        "kia": 0.93, "nissan": 0.93, "subaru": 0.95, "mazda": 0.94,
        "volkswagen": 0.94, "bmw": 0.92, "mercedes": 0.92, "audi": 0.92,
        "lexus": 0.95, "acura": 0.94,
    }
    ratio = invoice_ratios.get(make.lower(), 0.93)
    estimated_invoice = msrp * ratio
    target_offer = estimated_invoice * 1.02  # 2% over invoice is fair
    walk_away = msrp * 0.97  # Never pay more than 3% under MSRP for non-hot models

    verdict = None
    savings = None
    if dealer_offer:
        dealer_offer = float(dealer_offer)
        if dealer_offer <= target_offer:
            verdict = "BUY"
            savings = 0
        elif dealer_offer <= walk_away:
            verdict = "NEGOTIATE"
            savings = round(dealer_offer - target_offer)
        else:
            verdict = "WALK AWAY"
            savings = round(dealer_offer - target_offer)

    return {
        "estimated_invoice": round(estimated_invoice),
        "target_offer": round(target_offer),
        "walk_away_price": round(walk_away),
        "potential_savings": round(msrp - target_offer),
        "dealer_offer": round(float(dealer_offer)) if dealer_offer else None,
        "verdict": verdict,
        "savings_available": savings,
    }

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/report", methods=["POST"])
def report():
    data = request.json
    year  = data.get("year", "")
    make  = data.get("make", "").strip()
    model = data.get("model", "").strip()
    msrp  = data.get("msrp", "")
    dealer_offer = data.get("dealer_offer", "") or None
    annual_miles = int(data.get("annual_miles", 12000))

    recalls      = get_recalls(make, model, year)
    complaints   = get_complaints(make, model, year)
    fuel_economy = get_fuel_economy(make, model, year)
    true_cost    = calculate_true_cost(msrp, fuel_economy, annual_miles) if msrp else None
    negotiation  = get_negotiation_intel(make, model, year, msrp, dealer_offer) if msrp else None

    # Safety score based on recalls + complaints
    recall_count    = len(recalls)
    complaint_count = complaints.get("total", 0)
    if recall_count == 0 and complaint_count < 10:
        safety_signal = "GREEN"
    elif recall_count <= 2 and complaint_count < 50:
        safety_signal = "YELLOW"
    else:
        safety_signal = "RED"

    return jsonify({
        "vehicle": {"year": year, "make": make, "model": model},
        "recalls": recalls,
        "recall_count": recall_count,
        "complaints": complaints,
        "fuel_economy": fuel_economy,
        "true_cost": true_cost,
        "negotiation": negotiation,
        "safety_signal": safety_signal,
    })

@app.route("/makes")
def makes():
    year = request.args.get("year", "2021")
    try:
        r = requests.get(f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/make?year={year}",
                        headers={"Accept": "application/json"}, timeout=10)
        items = r.json().get("menuItem", [])
        return jsonify([i["value"] for i in items])
    except:
        return jsonify([])

@app.route("/models")
def models():
    year = request.args.get("year", "2021")
    make = request.args.get("make", "")
    try:
        r = requests.get(f"https://www.fueleconomy.gov/ws/rest/vehicle/menu/model?year={year}&make={make}",
                        headers={"Accept": "application/json"}, timeout=10)
        items = r.json().get("menuItem", [])
        return jsonify([i["value"] for i in items])
    except:
        return jsonify([])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
