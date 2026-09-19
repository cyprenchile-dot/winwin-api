from flask import Flask, request, jsonify, send_file
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
                pass
    return {
        "dailyLedger": [],
        "machines": []
    }

def save_data(data):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# Ruta raíz para cargar el panel visual index.html
@app.route('/')
def serve_index():
    return send_file('index.html')

# Ruta para recibir la telemetría del ESP32
@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    try:
        data = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": "JSON inválido"}), 400

    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    dev_id = data.get('device_id') or data.get('mac')
    if not dev_id:
        return jsonify({"error": "Falta identificador"}), 400

    try:
        coins_received = int(data.get('coins', 0))
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

    # Cada pulso equivale exactamente a 100 CLP
    if coins_received > 0:
        monto_clp = coins_received * 100
        machine["box"] = machine.get("box", 0) + monto_clp
        machine["sales"] = machine.get("sales", 0) + monto_clp
        print(f"💰 [MONEDA] +{monto_clp} CLP para {dev_id}. Total box: {machine['box']}")

    if prize_status == "dispense":
        machine["prizes"] = machine.get("prizes", 0) + 1
        print(f"🎁 [PREMIO] Registrado en {dev_id}")

    machine["wifi"] = wifi_signal
    machine["active"] = True

    save_data(db)

    return jsonify({"status": "success", "data": machine}), 200

# Ruta de sincronización para el frontend (soporta GET y POST)
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
