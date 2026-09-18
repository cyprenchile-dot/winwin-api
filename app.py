from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import json
import os

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_FILE = "fleet_database.json"

def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("Error leyendo base de datos:", e)
    return {"machines": [], "dailyLedger": []}

def save_db(data):
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print("Error guardando base de datos:", e)

# Ruta principal para servir el panel web directamente desde Render
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/telemetry', methods=['GET', 'POST'])
def handle_telemetry():
    fleet_state = load_db()
    if request.method == 'POST':
        data = request.get_json()
        if data:
            device_id = data.get('device_id')
            coins = data.get('coins', 0)
            prize = data.get('prize', '')

            machine = next((m for m in fleet_state["machines"] if m["mac"] == device_id), None)
            if not machine:
                machine = {
                    "mac": device_id,
                    "name": f"Terminal {device_id[-5:]}",
                    "sales": 0,
                    "box": 0,
                    "prizes": 0,
                    "wifi": data.get('wifi', -50),
                    "active": True,
                    "dailyLogs": {},
                    "withdrawalHistory": []
                }
                fleet_state["machines"].append(machine)

            if machine.get("active", True):
                if coins > 0:
                    machine["sales"] += coins * 100
                    machine["box"] += coins * 100
                if prize and prize != "":
                    machine["prizes"] = machine.get("prizes", 0) + 1
            
            if 'wifi' in data:
                machine["wifi"] = data['wifi']

            save_db(fleet_state)
            return jsonify({'success': True, 'message': 'Guardado en disco persistente'}), 200
        return jsonify({'success': False}), 400
    else:
        return jsonify(fleet_state), 200

@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    fleet_state = load_db()
    if request.method == 'POST':
        data = request.get_json()
        if data:
            if "machines" in data:
                fleet_state["machines"] = data["machines"]
            if "dailyLedger" in data:
                fleet_state["dailyLedger"] = data["dailyLedger"]
            save_db(fleet_state)
            return jsonify({'success': True}), 200
        return jsonify({'success': False}), 400
    else:
        return jsonify(fleet_state), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
