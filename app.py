import datetime
import random

from flask import Flask, jsonify, send_from_directory

from prediction import predict_levels

app = Flask(__name__, static_folder=None)


def generate_demo_candles(n=5, base=2400.0):
    """Synthetic OHLC candles used when no live MT5 connection is configured."""
    candles = []
    price = base
    for _ in range(n):
        o = price
        h = o + random.uniform(0.5, 4.0)
        l = o - random.uniform(0.5, 4.0)
        c = round(random.uniform(l, h), 2)
        candles.append({"open": round(o, 2), "high": round(h, 2), "low": round(l, 2), "close": c})
        price = c
    return candles


@app.get("/api/account")
def api_account():
    return jsonify({
        "balance": 10000.0,
        "equity": 10000.0,
        "profit": 0.0,
        "login": "demo",
        "server": "demo-server",
        "symbol": "XAUUSD.m",
        "updated": datetime.datetime.utcnow().isoformat() + "Z",
    })


@app.get("/api/positions")
def api_positions():
    return jsonify([])


@app.get("/api/ohlc")
def api_ohlc():
    return jsonify(generate_demo_candles())


@app.get("/api/prediction")
def api_prediction():
    candles = generate_demo_candles()
    levels = predict_levels(candles)
    return jsonify({"symbol": "XAUUSD.m", "candles": candles, **levels})


@app.get("/")
def index():
    return send_from_directory(".", "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
