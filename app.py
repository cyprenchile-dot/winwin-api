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
    return {
        "dailyLedger": [],
        "machines": []
    }

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
    
    if "machines" not in db:
        db["machines"] = []

    machine = None
    for m in db["machines"]:
        if m.get("mac") == dev_id or m.get("device_id") == dev_id:
            machine = m
            break

    if not machine:
        machine = {
            "mac": dev_id,
            "device_id": dev_id,
            "name": "Terminal 10:01",
            "active": True,
            "box": 0,
            "sales": 0,
            "prizes": 0,
            "wifi": wifi_signal,
            "dailyLogs": {},
            "withdrawalHistory": []
        }
        db["machines"].append(machine)

    # Cada pulso equivale exactamente a 100 CLP
    if coins_received > 0:
        monto_clp = coins_received * 100
        machine["box"] += monto_clp
        machine["sales"] += monto_clp
        print(f"💰 [MONEDA] ¡+{monto_clp} CLP sumados a {dev_id}! Total box: {machine['box']}")

    if prize_status == "dispense":
        machine["prizes"] += 1
        print(f"🎁 [PREMIO] ¡Premio registrado en {dev_id}!")

    machine["wifi"] = wifi_signal
    machine["active"] = True

    save_data(db)

    return jsonify({"status": "success", "data": machine}), 200

@app.route('/api/sync-fleet', methods=['GET'])
def sync_fleet():
    db = load_data()
    return jsonify(db), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return sync_fleet()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
