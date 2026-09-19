from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

DATABASE_FILE = 'fleet_database.json'

def load_data():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def save_data(data):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    dev_id = data.get('device_id') or data.get('mac')
    if not dev_id:
        return jsonify({"error": "Falta identificador"}), 400

    coins_received = int(data.get('coins', 0))
    wifi_signal = int(data.get('wifi', -60))
    prize_status = data.get('prize', '')

    db = load_data()

    if dev_id not in db:
        db[dev_id] = {
            "name": "Peluchera Mall Plaza",
            "active": True,
            "box_cash": 0,
            "daily_sales": 0,
            "prizes": 0,
            "wifi": wifi_signal,
            "status": "online"
        }

    # Cada pulso equivale exactamente a 100 CLP
    if coins_received > 0:
        monto_clp = coins_received * 100
        db[dev_id]["box_cash"] = db[dev_id].get("box_cash", 0) + monto_clp
        db[dev_id]["daily_sales"] = db[dev_id].get("daily_sales", 0) + monto_clp
        print(f"💰 [MONEDA] ¡+{monto_clp} CLP sumados a {dev_id}! Total caja: {db[dev_id]['box_cash']}")

    if prize_status == "dispense":
        db[dev_id]["prizes"] = db[dev_id].get("prizes", 0) + 1
        print(f"🎁 [PREMIO] ¡Premio registrado en {dev_id}!")

    db[dev_id]["wifi"] = wifi_signal
    db[dev_id]["status"] = "online"

    # Duplicar nombres de llaves para garantizar compatibilidad total con cualquier index.html
    db[dev_id]["caja"] = db[dev_id]["box_cash"]
    db[dev_id]["caja_fisica"] = db[dev_id]["box_cash"]
    db[dev_id]["ventas"] = db[dev_id]["daily_sales"]
    db[dev_id]["ventas_dia"] = db[dev_id]["daily_sales"]
    db[dev_id]["premios"] = db[dev_id]["prizes"]

    save_data(db)

    return jsonify({"status": "success", "data": db[dev_id]}), 200

@app.route('/api/sync-fleet', methods=['GET'])
def sync_fleet():
    return jsonify(load_data()), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(load_data()), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
