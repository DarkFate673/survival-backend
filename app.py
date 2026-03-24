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

    daily_water = people * 3
    days = water / daily_water if daily_water > 0 else 0

    return jsonify({"days": round(days, 2)})
