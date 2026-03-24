from flask import Flask, request, jsonify, render_template

app = Flask(__name__)


def safe_div(a, b):
    return round(a / b, 2) if b else 0


def build_analysis(data):
    people = max(int(data.get("people", 1) or 1), 1)

    water = float(data.get("water", 0) or 0)      # litres
    food = float(data.get("food", 0) or 0)        # calories
    fuel = float(data.get("fuel", 0) or 0)        # grams
    medical = float(data.get("medical", 0) or 0)  # coverage days

    activity = str(data.get("activity", "medium")).lower()
    climate = str(data.get("climate", "mild")).lower()
    cooking = bool(data.get("cooking", True))
    water_access = str(data.get("water_access", "none")).lower()

    # Base daily requirements
    water_per_person = 3.0
    food_per_person = 2000.0
    fuel_per_person = 50.0 if cooking else 10.0

    # Activity modifiers
    if activity == "low":
        food_per_person *= 0.9
        water_per_person *= 0.95
    elif activity == "high":
        food_per_person *= 1.3
        water_per_person *= 1.25
        fuel_per_person *= 1.15

    # Climate modifiers
    if climate == "hot":
        water_per_person *= 1.35
    elif climate == "cold":
        fuel_per_person *= 1.5
        food_per_person *= 1.1

    # Water access modifier
    water_refill_per_day = 0.0
    if water_access == "limited":
        water_refill_per_day = people * 0.75
    elif water_access == "yes":
        water_refill_per_day = people * 1.5

    water_daily = round(people * water_per_person, 2)
    food_daily = round(people * food_per_person, 2)
    fuel_daily = round(people * fuel_per_person, 2)

    effective_water_daily = max(water_daily - water_refill_per_day, 0.1)

    coverage = {
        "water": safe_div(water, effective_water_daily),
        "food": safe_div(food, food_daily),
        "fuel": safe_div(fuel, fuel_daily),
        "medical": round(medical, 2),
    }

    weakest = min(coverage, key=coverage.get)
    survivable_days = round(coverage[weakest], 2)

    if survivable_days > 7:
        status = "READY"
    elif survivable_days > 3:
        status = "TIGHT"
    else:
        status = "CRITICAL"

    return {
        "inputs": {
            "people": people,
            "activity": activity,
            "climate": climate,
            "cooking": cooking,
            "water_access": water_access,
        },
        "resources": {
            "water": round(water, 2),
            "food": round(food, 2),
            "fuel": round(fuel, 2),
            "medical": round(medical, 2),
        },
        "daily": {
            "water": water_daily,
            "food": food_daily,
            "fuel": fuel_daily,
            "water_refill": round(water_refill_per_day, 2),
            "effective_water": round(effective_water_daily, 2),
        },
        "coverage": coverage,
        "weakest": weakest,
        "survivable_days": survivable_days,
        "status": status,
    }


def build_recommendations(analysis, target_days):
    recs = []
    coverage = analysis["coverage"]
    daily = analysis["daily"]
    weakest = analysis["weakest"]
    survivable_days = analysis["survivable_days"]
    resources = analysis["resources"]
    inputs = analysis["inputs"]

    if target_days and survivable_days < target_days:
        recs.append(
            f"Target gap: you are short by {round(target_days - survivable_days, 2)} days."
        )

    if coverage["water"] < target_days:
        shortfall = max((target_days * daily["effective_water"]) - resources["water"], 0)
        recs.append(f"Add {round(shortfall, 2)}L water to reach {target_days} days.")

    if coverage["food"] < target_days:
        shortfall = max((target_days * daily["food"]) - resources["food"], 0)
        recs.append(f"Add {round(shortfall, 0)} calories to reach {target_days} days.")

    if coverage["fuel"] < target_days:
        shortfall = max((target_days * daily["fuel"]) - resources["fuel"], 0)
        recs.append(f"Add {round(shortfall, 0)}g fuel to reach {target_days} days.")

    if coverage["medical"] < target_days:
        shortfall = max(target_days - resources["medical"], 0)
        recs.append(f"Add {round(shortfall, 2)} days of medical coverage.")

    if inputs["cooking"] and coverage["fuel"] <= coverage["food"]:
        recs.append("Switch some meals to no-cook options to extend fuel coverage.")

    if inputs["climate"] == "hot":
        recs.append("Hot climate detected: prioritize extra water before all other upgrades.")

    if weakest == "medical":
        recs.append("Medical is the primary failure point. Treat this as highest priority.")

    if not recs:
        recs.append("System is balanced against the selected target. Maintain redundancy.")

    return recs[:6]


def build_simulation(analysis, target_days):
    days_to_run = max(int(target_days or 14), 1)

    water = analysis["resources"]["water"]
    food = analysis["resources"]["food"]
    fuel = analysis["resources"]["fuel"]
    medical_days_left = analysis["resources"]["medical"]

    water_daily = analysis["daily"]["effective_water"]
    food_daily = analysis["daily"]["food"]
    fuel_daily = analysis["daily"]["fuel"]

    timeline = []

    for day in range(1, days_to_run + 1):
        water = round(max(water - water_daily, 0), 2)
        food = round(max(food - food_daily, 0), 2)
        fuel = round(max(fuel - fuel_daily, 0), 2)
        medical_days_left = round(max(medical_days_left - 1, 0), 2)

        failures = []
        if water <= 0:
            failures.append("water")
        if food <= 0:
            failures.append("food")
        if fuel <= 0:
            failures.append("fuel")
        if medical_days_left <= 0:
            failures.append("medical")

        timeline.append(
            {
                "day": day,
                "water": water,
                "food": food,
                "fuel": fuel,
                "medical": medical_days_left,
                "failures": failures,
                "collapse": len(failures) > 0,
            }
        )

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
        "failure_resource": failure_resource,
    }


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json or {}
    target_days = int(data.get("target_days", 7) or 7)

    analysis = build_analysis(data)
    recommendations = build_recommendations(analysis, target_days)
    simulation = build_simulation(analysis, target_days)

    return jsonify(
        {
            **analysis,
            "target_days": target_days,
            "recommendations": recommendations,
            "simulation": simulation,
        }
    )


if __name__ == "__main__":
    app.run(debug=True)
