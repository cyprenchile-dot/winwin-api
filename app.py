from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import json
import os
import time

app = Flask(__name__)
CORS(app)

DATABASE_FILE = 'fleet_database.json'

DEFAULT_DATABASE = {
    "dailyLedger": [],
    "machines": []
}

def load_data():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict) and "machines" in data:
                    return data
        except Exception as e:
            print(f"⚠️ Error leyendo JSON: {e}")
    
    save_data(DEFAULT_DATABASE)
    return DEFAULT_DATABASE

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
        return jsonify({"error": "JSON inválido"}), 400

    if not data:
        return jsonify({"error": "JSON vacío"}), 400

    dev_id = data.get('device_id') or data.get('mac')
    if not dev_id:
        return jsonify({"error": "Falta identificador"}), 400

    # 🚫 LISTA NEGRA: Bloqueo definitivo para que la Terminal 6254 no vuelva a crearse jamás
    BLOCKED_MACS = ["20:50:0D:30:62:54"]
    if dev_id in BLOCKED_MACS:
        return jsonify({"status": "ignored", "message": "Terminal bloqueada"}), 200

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
            "name": f"Terminal {dev_id[-5:] if len(dev_id)>=5 else 'Nuevo'}",
            "location": "Local por definir",
            "lat": -33.4489,
            "lng": -70.6693,
            "active": True,
            "box": 0,
            "sales": 0,
            "prizes": 0,
            "wifi": wifi_signal,
            "last_seen": time.time(),
            "dailyLogs": {},
            "withdrawalHistory": []
        }
        db["machines"].append(machine)

    if coins_received > 0:
        monto_clp = coins_received * 100
        machine["box"] = machine.get("box", 0) + monto_clp
        machine["sales"] = machine.get("sales", 0) + monto_clp

    if prize_status == "dispense":
        machine["prizes"] = machine.get("prizes", 0) + 1

    machine["wifi"] = wifi_signal
    machine["last_seen"] = time.time()

    save_data(db)
    return jsonify({"status": "success", "box": machine["box"], "sales": machine["sales"]}), 200

@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            if data and isinstance(data, dict):
                # Limpiar cualquier intento de sincronizar la MAC bloqueada
                if "machines" in data:
                    data["machines"] = [m for m in data["machines"] if m.get("mac") not in ["20:50:0D:30:62:54"]]
                save_data(data)
                return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"error": "Datos inválidos"}), 400
    else:
        db = load_data()
        current_time = time.time()
        
        # Filtrar preventivamente la MAC bloqueada de la lista devuelta
        if "machines" in db:
            db["machines"] = [m for m in db["machines"] if m.get("mac") not in ["20:50:0D:30:62:54"]]

        # Cálculo preciso de estado online/offline (menos de 35 segundos desde último latido)
        for m in db.get("machines", []):
            last_seen = m.get("last_seen", 0)
            if last_seen > 0 and (current_time - last_seen) <= 35:
                m["is_online"] = True
            else:
                m["is_online"] = False

        return jsonify(db), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return sync_fleet()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
