import atexit
import datetime
import os
import threading

from flask import Flask, jsonify, request, send_from_directory
import MetaTrader5 as mt5

from prediction import predict_levels

app = Flask(__name__, static_folder=None)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MT5_LOGIN = os.environ.get("MT5_LOGIN")
MT5_PASSWORD = os.environ.get("MT5_PASSWORD")
MT5_SERVER = os.environ.get("MT5_SERVER")
MT5_SYMBOL = os.environ.get("MT5_SYMBOL", "XAUUSD.m")

# Real trading is opt-in only: with this unset (the default), the auto-loop
# computes and logs what it *would* place but never calls order_send().
AUTO_TRADE_ENABLED = os.environ.get("MT5_AUTOTRADE_ENABLED", "0") == "1"
MAGIC = 20240701

TIMEFRAME_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

# The MetaTrader5 package wraps a single process-wide terminal connection
# (not one per call), so every request handler and the auto-loop thread
# share it through this lock instead of each connecting/disconnecting on
# their own — concurrent init/shutdown calls would tear down each other's
# session mid-use.
mt5_lock = threading.Lock()
_connected = False


def ensure_connected():
    global _connected
    if not (MT5_LOGIN and MT5_PASSWORD and MT5_SERVER):
        raise RuntimeError(
            "Set MT5_LOGIN, MT5_PASSWORD and MT5_SERVER environment variables before starting the server."
        )
    try:
        login_id = int(MT5_LOGIN)
    except ValueError:
        raise RuntimeError("MT5_LOGIN must be an integer account number")
    if _connected:
        return
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    if not mt5.login(login_id, MT5_PASSWORD, MT5_SERVER):
        err = mt5.last_error()
        raise RuntimeError(f"MT5 login failed: {err}")
    _connected = True


atexit.register(mt5.shutdown)


def fetch_last_5_candles(symbol, timeframe):
    # start_pos=1 skips the current, still-forming candle so all 5 used by
    # predict_levels() are fully closed.
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 1, 5)
    if rates is None or len(rates) < 5:
        raise RuntimeError("Not enough candle history returned by MT5")
    return [
        {"open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"])}
        for r in rates
    ]


def get_current_bar_time(symbol, timeframe):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 1)
    if rates is None or len(rates) < 1:
        raise RuntimeError("Could not read current bar")
    return int(rates[0]["time"])


def round_price(symbol, price):
    info = mt5.symbol_info(symbol)
    digits = info.digits if info else 2
    return round(price, digits)


@app.get("/api/account")
def api_account():
    try:
        with mt5_lock:
            ensure_connected()
            info = mt5.account_info()
            if info is None:
                return jsonify({"error": "account_info_unavailable"}), 500
            return jsonify({
                "login": str(info.login),
                "server": info.server,
                "balance": info.balance,
                "equity": info.equity,
                "profit": info.profit,
            })
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/positions")
def api_positions():
    try:
        with mt5_lock:
            ensure_connected()
            positions = mt5.positions_get(symbol=MT5_SYMBOL) or []
            return jsonify([
                {
                    "ticket": p.ticket,
                    "type": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                    "volume": p.volume,
                    "price_open": p.price_open,
                    "sl": p.sl,
                    "tp": p.tp,
                    "profit": p.profit,
                }
                for p in positions
            ])
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/ohlc")
def api_ohlc():
    try:
        with mt5_lock:
            ensure_connected()
            return jsonify(fetch_last_5_candles(MT5_SYMBOL, mt5.TIMEFRAME_M15))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/prediction")
def api_prediction():
    try:
        with mt5_lock:
            ensure_connected()
            candles = fetch_last_5_candles(MT5_SYMBOL, mt5.TIMEFRAME_M15)
        levels = predict_levels(candles)
        return jsonify({"symbol": MT5_SYMBOL, "candles": candles, **levels})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.get("/api/timeframes")
def api_timeframes():
    return jsonify(list(TIMEFRAME_MAP.keys()))


# --- Auto-loop -------------------------------------------------------------
# Polls the current bar's open time every few seconds; when it changes, the
# previous bar just closed, so the last 5 closed candles are re-fetched,
# predict_levels() re-run, and (only if MT5_AUTOTRADE_ENABLED=1) a fresh
# BUY_LIMIT/SELL_LIMIT pair with SL/TP is placed, replacing any still-open
# pending orders from the prior candle.

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


def cancel_order(ticket):
    mt5.order_send({"action": mt5.TRADE_ACTION_REMOVE, "order": ticket})


def place_pending(symbol, order_type, price, sl, tp, volume, comment):
    return mt5.order_send({
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": round_price(symbol, price),
        "sl": round_price(symbol, sl),
        "tp": round_price(symbol, tp),
        "magic": MAGIC,
        "comment": comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    })


def auto_loop(symbol, timeframe_key, volume, sl_buffer_atr):
    timeframe = TIMEFRAME_MAP[timeframe_key]
    log_event(f"auto-loop started: {symbol} {timeframe_key} ({'LIVE orders' if AUTO_TRADE_ENABLED else 'dry-run'})")
    last_open_time = None
    pending_tickets = []
    try:
        while not auto_stop_event.is_set():
            try:
                with mt5_lock:
                    ensure_connected()
                    latest_open_time = get_current_bar_time(symbol, timeframe)
                    is_new_candle = last_open_time is not None and latest_open_time != last_open_time
                    candles = fetch_last_5_candles(symbol, timeframe) if is_new_candle else None

                if last_open_time is None:
                    last_open_time = latest_open_time
                elif is_new_candle:
                    last_open_time = latest_open_time
                    levels = predict_levels(candles)
                    with auto_state_lock:
                        auto_state["last_candles"] = candles
                        auto_state["last_levels"] = levels
                        auto_state["last_candle_time"] = latest_open_time

                    with mt5_lock:
                        for ticket in pending_tickets:
                            cancel_order(ticket)
                        pending_tickets = []

                        if AUTO_TRADE_ENABLED:
                            sl_buy = levels["predicted_low"] - sl_buffer_atr * levels["atr"]
                            sl_sell = levels["predicted_high"] + sl_buffer_atr * levels["atr"]
                            orders = [
                                ("buy_limit", mt5.ORDER_TYPE_BUY_LIMIT, levels["buy_limit"], sl_buy, levels["sell_limit"]),
                                ("sell_limit", mt5.ORDER_TYPE_SELL_LIMIT, levels["sell_limit"], sl_sell, levels["buy_limit"]),
                            ]
                            for label, order_type, price, sl, tp in orders:
                                r = place_pending(symbol, order_type, price, sl, tp, volume, "auto-predict")
                                if r is not None and r.retcode == mt5.TRADE_RETCODE_DONE:
                                    pending_tickets.append(r.order)
                                    log_event(f"{label} placed @ {price:.2f} (sl {sl:.2f} / tp {tp:.2f}) ticket={r.order}")
                                else:
                                    log_event(f"{label} FAILED: {getattr(r, 'comment', r)}")
                        else:
                            log_event(
                                f"dry-run: buy_limit={levels['buy_limit']:.2f} sell_limit={levels['sell_limit']:.2f} "
                                "(set MT5_AUTOTRADE_ENABLED=1 to place live orders)"
                            )
            except RuntimeError as e:
                log_event(f"error: {e}")
            auto_stop_event.wait(5)
    finally:
        if pending_tickets:
            try:
                with mt5_lock:
                    for ticket in pending_tickets:
                        cancel_order(ticket)
            except Exception:
                pass
        with auto_state_lock:
            auto_state["running"] = False
        log_event("auto-loop stopped")


@app.get("/api/auto/status")
def api_auto_status():
    with auto_state_lock:
        return jsonify({**auto_state, "live_trading": AUTO_TRADE_ENABLED})


@app.post("/api/auto/start")
def api_auto_start():
    global auto_thread
    data = request.get_json(silent=True) or {}
    timeframe_key = data.get("timeframe", "M15")
    if timeframe_key not in TIMEFRAME_MAP:
        return jsonify({"error": "invalid_timeframe"}), 400
    try:
        volume = float(data.get("volume", 0.01))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_volume"}), 400
    try:
        sl_buffer_atr = float(data.get("sl_buffer_atr", 0.5))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_sl_buffer_atr"}), 400

    with auto_state_lock:
        if auto_state["running"]:
            return jsonify({"error": "already_running"}), 409
        auto_state["running"] = True
        auto_state["timeframe"] = timeframe_key
        auto_state["last_candle_time"] = None
        auto_state["last_candles"] = None
        auto_state["last_levels"] = None

    auto_stop_event.clear()
    auto_thread = threading.Thread(
        target=auto_loop, args=(MT5_SYMBOL, timeframe_key, volume, sl_buffer_atr), daemon=True
    )
    auto_thread.start()
    return jsonify({"status": "started", "timeframe": timeframe_key, "live_trading": AUTO_TRADE_ENABLED})


@app.post("/api/auto/stop")
def api_auto_stop():
    auto_stop_event.set()
    return jsonify({"status": "stopping"})


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False, threaded=True)
