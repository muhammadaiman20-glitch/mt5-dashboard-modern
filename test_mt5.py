from flask import Flask, jsonify
import MetaTrader5 as mt5

app = Flask(__name__)

@app.get('/api/account')
def api_account():
    if not mt5.initialize():
        return jsonify({'error': 'init_failed', 'last_error': mt5.last_error()}), 500
    if not mt5.login(1100400783, 'Asdf1234.', 'JustMarkets-Live2'):
        return jsonify({'error': 'login_failed', 'last_error': mt5.last_error()}), 500
    info = mt5.account_info()
    mt5.shutdown()
    return jsonify({'login': str(info.login), 'server': info.server, 'balance': info.balance})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081, debug=False)
