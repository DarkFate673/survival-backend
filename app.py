from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/calculate", methods=["POST"])
def calculate():
    data = request.json

    people = data.get("people", 1)

    water = data.get("water", 0)
    food = data.get("food", 0)        # calories
    fuel = data.get("fuel", 0)        # grams
    medical = data.get("medical", 0)  # days

    # Daily requirements
    water_daily = people * 3
    food_daily = people * 2000
    fuel_daily = people * 50

    # Coverage
    water_days = water / water_daily if water_daily else 0
    food_days = food / food_daily if food_daily else 0
    fuel_days = fuel / fuel_daily if fuel_daily else 0
    medical_days = medical

    coverage = {
        "water": water_days,
        "food": food_days,
        "fuel": fuel_days,
        "medical": medical_days
    }

    # Weakest link
    weakest = min(coverage, key=coverage.get)
    survivable_days = coverage[weakest]

    # Status
    if survivable_days > 7:
        status = "READY"
    elif survivable_days > 3:
        status = "TIGHT"
    else:
        status = "CRITICAL"

    return jsonify({
        "survivable_days": round(survivable_days, 2),
        "weakest": weakest,
        "status": status,
        "coverage": coverage
    })
