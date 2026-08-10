import datetime
import os
import random
import threading

from flask import Flask, jsonify, request, send_from_directory

from prediction import predict_levels

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TIMEFRAMES = ["M1", "M5", "M15", "M30", "H1", "H4", "D1"]


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


@app.get("/api/timeframes")
def api_timeframes():
    return jsonify(TIMEFRAMES)


# --- Auto-loop (simulated) --------------------------------------------------
# There's no live MT5 connection in demo mode, so this just re-generates a
# synthetic "closed candle" on a fixed cadence and recomputes predict_levels()
# — it mirrors the same /api/auto/* interface test_mt5.py exposes for real
# trading, but never places orders (live_trading is always false here).

auto_state_lock = threading.Lock()
auto_stop_event = threading.Event()
auto_thread = None
auto_state = {
    "running": False,
    "timeframe": None,
    "last_candle_time": None,
    "last_candles": None,
    "last_levels": None,
    "log": [],
}


def log_event(msg):
    ts = datetime.datetime.utcnow().isoformat() + "Z"
    with auto_state_lock:
        auto_state["log"].insert(0, f"{ts} {msg}")
        auto_state["log"] = auto_state["log"][:50]


def demo_auto_loop(timeframe_key):
    log_event(f"demo auto-loop started ({timeframe_key})")
    while not auto_stop_event.is_set():
        candles = generate_demo_candles()
        levels = predict_levels(candles)
        now = datetime.datetime.utcnow().isoformat() + "Z"
        with auto_state_lock:
            auto_state["last_candles"] = candles
            auto_state["last_levels"] = levels
            auto_state["last_candle_time"] = now
        log_event(f"demo candle closed: buy_limit={levels['buy_limit']:.2f} sell_limit={levels['sell_limit']:.2f}")
        auto_stop_event.wait(10)
    with auto_state_lock:
        auto_state["running"] = False
    log_event("demo auto-loop stopped")


@app.get("/api/auto/status")
def api_auto_status():
    with auto_state_lock:
        return jsonify({**auto_state, "live_trading": False})


@app.post("/api/auto/start")
def api_auto_start():
    global auto_thread
    data = request.get_json(silent=True) or {}
    timeframe_key = data.get("timeframe", "M15")
    if timeframe_key not in TIMEFRAMES:
        return jsonify({"error": "invalid_timeframe"}), 400

    with auto_state_lock:
        if auto_state["running"]:
            return jsonify({"error": "already_running"}), 409
        auto_state["running"] = True
        auto_state["timeframe"] = timeframe_key
        auto_state["last_candle_time"] = None
        auto_state["last_candles"] = None
        auto_state["last_levels"] = None

    auto_stop_event.clear()
    auto_thread = threading.Thread(target=demo_auto_loop, args=(timeframe_key,), daemon=True)
    auto_thread.start()
    return jsonify({"status": "started", "timeframe": timeframe_key, "live_trading": False})


@app.post("/api/auto/stop")
def api_auto_stop():
    auto_stop_event.set()
    return jsonify({"status": "stopping"})


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False, threaded=True)
