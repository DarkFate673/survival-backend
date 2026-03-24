from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


# -----------------------------
# CORE HELPERS
# -----------------------------
def safe_div(a, b):
    return round(a / b, 2) if b else 0


# -----------------------------
# CONSUMPTION ENGINE
# -----------------------------
def get_daily_usage(inputs):
    people = inputs["people"]
    activity = inputs["activity"]
    climate = inputs["climate"]
    cooking = inputs["cooking"]

    # Base
    water = 3.0
    food = 2000.0
    fuel = 0.5 if cooking else 0.1  # litres/petrol/diesel
    gas = 0.15 if cooking else 0

    # Activity
    if activity == "high":
        water *= 1.25
        food *= 1.3
        fuel *= 1.15
        gas *= 1.1   # optional but consistent
    elif activity == "low":
        water *= 0.95
        food *= 0.9

    # Climate
    if climate == "hot":
        water *= 1.35
    elif climate == "cold":
        fuel *= 1.5
        food *= 1.1

    return {
        "water": round(water * people, 2),
        "food": round(food * people, 2),
        "fuel": round(fuel * people, 2),
        "gas": round(gas * people, 2)
    }


# -----------------------------
# COVERAGE ENGINE
# -----------------------------
def get_coverage(resources, daily):
    return {
        "water": safe_div(resources["water"], daily["water"]),
        "food": safe_div(resources["food"], daily["food"]),
        "fuel": safe_div(resources["fuel_total"], daily["fuel"]),
        "gas": safe_div(resources["gas"], daily["gas"]) if daily["gas"] > 0 else 999,
        "medical": resources["medical"]
    }


# -----------------------------
# WEAKEST LINK
# -----------------------------
def get_weakest(coverage):
    weakest = min(coverage, key=coverage.get)
    return weakest, round(coverage[weakest], 2)


# -----------------------------
# SIMULATION ENGINE (FIXED)
# -----------------------------
def simulate(resources, daily, target_days):
    timeline = []

    water = resources["water"]
    food = resources["food"]
    petrol = resources["petrol"]
    diesel = resources["diesel"]
    gas = resources["gas"]  # FIX: initialize gas
    medical = resources["medical"]]

    fuel_daily = daily["fuel"]

    for day in range(1, target_days + 1):

        # depletion
        water -= daily["water"]
        food -= daily["food"]

        # split fuel usage (REAL FIX)
        total_fuel = petrol + diesel
        if total_fuel > 0:
            petrol -= fuel_daily * (petrol / total_fuel)
            diesel -= fuel_daily * (diesel / total_fuel)
        # FIX: gas depletion per day
        gas -= daily["gas"]
        
        medical -= 1

        water = max(water, 0)
        food = max(food, 0)
        petrol = max(petrol, 0)
        diesel = max(diesel, 0)
        gas = max(gas, 0
        medical = max(medical, 0)

        fuel_total = petrol + diesel

        failures = []
        if water <= 0:
            failures.append("water")
        if food <= 0:
            failures.append("food")
        if fuel_total <= 0:
            failures.append("fuel")
        if gas <= 0:  # FIX: include gas failure
            failures.append("gas")    
        if medical <= 0:
            failures.append("medical")

        timeline.append({
            "day": day,
            "water": round(water, 2),
            "food": round(food, 2),
            "petrol": round(petrol, 2),
            "diesel": round(diesel, 2),
            "fuel_total": round(fuel_total, 2),
            "gas": round(gas, 2),  # FIX: include gas in output
            "medical": round(medical, 2),
            "collapse": len(failures) > 0,
            "failures": failures
        })

        if failures:
            break

    collapse_day = None
    failure_resource = None

    for row in timeline:
        if row["collapse"]:
            collapse_day = row["day"]
            failure_resource = ", ".join(row["failures"])
            break

    return {
        "timeline": timeline,
        "collapse_day": collapse_day,
        "failure_resource": failure_resource
    }


# -----------------------------
# RECOMMENDATION ENGINE
# -----------------------------
def get_recommendations(coverage, target_days):
    recs = []

    if coverage["water"] < target_days:
        recs.append("Increase water supply")

    if coverage["food"] < target_days:
        recs.append("Increase calorie reserves")

    if coverage["fuel"] < target_days:
        recs.append("Increase fuel or reduce cooking")

    if coverage["medical"] < target_days:
        recs.append("Increase medical coverage")

    if not recs:
        recs.append("System balanced")

    return recs


# -----------------------------
# MAIN ANALYSIS
# -----------------------------
def analyze(data):

    inputs = {
        "people": max(int(data.get("people", 1)), 1),
        "activity": data.get("activity", "medium"),
        "climate": data.get("climate", "mild"),
        "cooking": data.get("cooking", True)
    }

    resources = {
        "water": float(data.get("water", 0)),
        "food": float(data.get("food", 0)),
        "petrol": float(data.get("petrol", 0)),
        "diesel": float(data.get("diesel", 0)),
        "gas": float(data.get("gas", 0)),
        "medical": float(data.get("medical", 0))
    }

    resources["fuel_total"] = resources["petrol"] + resources["diesel"]

    daily = get_daily_usage(inputs)
    coverage = get_coverage(resources, daily)

    weakest, survivable_days = get_weakest(coverage)

    if survivable_days > 7:
        status = "READY"
    elif survivable_days > 3:
        status = "TIGHT"
    else:
        status = "CRITICAL"

    return inputs, resources, daily, coverage, weakest, survivable_days, status


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json or {}
    target_days = int(data.get("target_days", 7))

    inputs, resources, daily, coverage, weakest, survivable_days, status = analyze(data)

    simulation = simulate(resources, daily, target_days)
    recs = get_recommendations(coverage, target_days)

    return jsonify({
        "inputs": inputs,
        "resources": resources,
        "daily": daily,
        "coverage": coverage,
        "weakest": weakest,
        "survivable_days": survivable_days,
        "status": status,
        "simulation": simulation,
        "recommendations": recs
    })


if __name__ == "__main__":
    app.run(debug=True)
