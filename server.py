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
                data = json.load(f)
                if isinstance(data, dict):
                    if "machines" not in data:
                        data["machines"] = []
                    if "dailyLedger" not in data:
                        data["dailyLedger"] = []
                    if "auditLogs" not in data:
                        data["auditLogs"] = []
                    return data
            except:
                pass
    # Estructura base inicial
    return {
        "dailyLedger": [],
        "machines": [],
        "auditLogs": []
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
    if "auditLogs" not in db:
        db["auditLogs"] = []

    machine = None
    for m in db["machines"]:
        if m.get("mac") == dev_id or m.get("device_id") == dev_id:
            machine = m
            break

    if not machine:
        machine = {
            "mac": dev_id,
            "device_id": dev_id,
            "name": f"Terminal {dev_id[-5:]}",
            "active": True,
            "box": 0,
            "sales": 0,
            "prizes": 0,
            "wifi": wifi_signal,
            "dailyLogs": {},
            "withdrawalHistory": []
        }
        db["machines"].append(machine)

    if coins_received > 0:
        monto_clp = coins_received * 100
        machine["box"] += monto_clp
        machine["sales"] += monto_clp

    if prize_status == "dispense":
        machine["prizes"] += 1

    machine["wifi"] = wifi_signal
    machine["active"] = True

    save_data(db)

    return jsonify({"status": "success", "data": machine}), 200

# Ruta de sincronización con soporte GET y POST para guardar máquinas, bitácoras y auditoría
@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    db = load_data()
    if request.method == 'POST':
        req_data = request.get_json(force=True)
        if req_data:
            if "machines" in req_data:
                db["machines"] = req_data["machines"]
            if "dailyLedger" in req_data:
                db["dailyLedger"] = req_data["dailyLedger"]
            if "auditLogs" in req_data:
                db["auditLogs"] = req_data["auditLogs"]
            save_data(db)
        return jsonify({"status": "synced", "data": db}), 200
    return jsonify(db), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return sync_fleet()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
