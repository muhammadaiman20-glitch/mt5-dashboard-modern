from flask import Flask, jsonify, render_template, send_from_directory
import datetime

app = Flask(__name__, static_folder="public", template_folder="public")

@app.get("/api/account")
def api_account():
    return jsonify({
        "balance": 10000.0,
        "equity": 10000.0,
        "profit": 0.0,
        "login": "1100400783",
        "server": "JustMarkets-Live2",
        "symbol": "XAUUSD.m",
        "updated": datetime.datetime.utcnow().isoformat() + "Z"
    })

@app.get("/api/positions")
def api_positions():
    return jsonify([])

@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.get("/<path:path>")
def assets(path):
    return send_from_directory(app.static_folder, path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
