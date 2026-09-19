from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)

DATABASE_FILE = 'fleet_database.json'

def load_data():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and "machines" in data:
                    return data
        except Exception as e:
            print(f"⚠️ Error leyendo JSON: {e}")
    return {
        "dailyLedger": [],
        "machines": []
    }

def save_data(data):
    try:
        with open(DATABASE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️ Error guardando JSON: {e}")

@app.route('/')
def serve_index():
    return send_file('index.html')

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        print(f"❌ Error al parsear JSON: {e}")
        return jsonify({"error": "JSON inválido"}), 400

    print(f"📥 [DATOS]: {data}")
    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    dev_id = data.get('device_id') or data.get('mac')
    if not dev_id:
        return jsonify({"error": "Falta identificador"}), 400

    try:
        coins_received = int(data.get('coins') or data.get('pulse') or 0)
    except:
        coins_received = 0

    try:
        wifi_signal = int(data.get('wifi', -60))
    except:
        wifi_signal = -60

    prize_status = str(data.get('prize', ''))

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

    if coins_received > 0:
        monto_clp = coins_received * 100
        machine["box"] = machine.get("box", 0) + monto_clp
        machine["sales"] = machine.get("sales", 0) + monto_clp
        print(f"💰 Sumados +{monto_clp} CLP. Total caja: {machine['box']}")

    if prize_status == "dispense":
        machine["prizes"] = machine.get("prizes", 0) + 1

    machine["wifi"] = wifi_signal
    machine["active"] = True

    save_data(db)
    return jsonify({"status": "success", "box": machine["box"], "sales": machine["sales"]}), 200

@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            if data:
                save_data(data)
                return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"error": "Datos inválidos"}), 400
    else:
        db = load_data()
        return jsonify(db), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return sync_fleet()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
