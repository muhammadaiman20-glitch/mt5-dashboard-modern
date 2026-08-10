import os

from flask import Flask, jsonify
import MetaTrader5 as mt5

from prediction import predict_levels

app = Flask(__name__, static_folder=None)

MT5_LOGIN = os.environ.get("MT5_LOGIN")
MT5_PASSWORD = os.environ.get("MT5_PASSWORD")
MT5_SERVER = os.environ.get("MT5_SERVER")
MT5_SYMBOL = os.environ.get("MT5_SYMBOL", "XAUUSD.m")


def mt5_connect():
    if not (MT5_LOGIN and MT5_PASSWORD and MT5_SERVER):
        raise RuntimeError(
            "Set MT5_LOGIN, MT5_PASSWORD and MT5_SERVER environment variables before starting the server."
        )
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    if not mt5.login(int(MT5_LOGIN), MT5_PASSWORD, MT5_SERVER):
        err = mt5.last_error()
        mt5.shutdown()
        raise RuntimeError(f"MT5 login failed: {err}")


def fetch_last_5_candles(symbol, timeframe=mt5.TIMEFRAME_M15):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 5)
    if rates is None or len(rates) < 5:
        raise RuntimeError("Not enough candle history returned by MT5")
    return [
        {"open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"])}
        for r in rates
    ]


@app.get("/api/account")
def api_account():
    try:
        mt5_connect()
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
    finally:
        mt5.shutdown()


@app.get("/api/ohlc")
def api_ohlc():
    try:
        mt5_connect()
        return jsonify(fetch_last_5_candles(MT5_SYMBOL))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    finally:
        mt5.shutdown()


@app.get("/api/prediction")
def api_prediction():
    try:
        mt5_connect()
        candles = fetch_last_5_candles(MT5_SYMBOL)
        levels = predict_levels(candles)
        return jsonify({"symbol": MT5_SYMBOL, "candles": candles, **levels})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=False)
