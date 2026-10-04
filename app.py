from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import time

app = Flask(__name__)
CORS(app)

DATABASE_FILE = '/var/data/fleet_database.json'

DEFAULT_DATABASE = {
    "dailyLedger": [],
    "machines": [],
    "auditLogs": []
}

def load_data():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"⚠️ Error leyendo JSON persistente: {e}")
    
    if not os.path.exists(DATABASE_FILE):
        save_data(DEFAULT_DATABASE)
    return DEFAULT_DATABASE

def save_data(data):
    try:
        os.makedirs(os.path.dirname(DATABASE_FILE), exist_ok=True)
        with open(DATABASE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"⚠️ Error crítico guardando en disco persistente: {e}")

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            if data and isinstance(data, dict):
                db = load_data()
                current_t = time.time()
                
                # 1. Reporte directo por pulso desde el ESP32
                if "mac" in data and "machines" not in data:
                    mac = data.get("mac")
                    machine_found = False
                    for m in db.get("machines", []):
                        if m.get("mac") == mac:
                            machine_found = True
                            if "sales" in data: m["sales"] = data["sales"]
                            if "wifi" in data: m["wifi"] = data["wifi"]
                            if "prizes" in data: m["prizes"] = data["prizes"]
                            m["last_seen"] = current_t
                            m["is_online"] = True
                    
                    if not machine_found:
                        new_m = {
                            "mac": mac,
                            "name": data.get("name", f"Terminal {mac[-5:]}"),
                            "location": data.get("location", "Local Terreno"),
                            "sales": data.get("sales", 0),
                            "wifi": data.get("wifi", -50),
                            "prizes": data.get("prizes", 0),
                            "active": True,
                            "is_online": True,
                            "last_seen": current_t,
                            "coinInitial": 3768,
                            "dailyLogs": {}
                        }
                        db["machines"].append(new_m)
                    
                    save_data(db)
                    return jsonify({"status": "success", "mode": "esp32_direct"}), 200

                # 2. Sincronización desde la interfaz web
                incoming_machines = data.get("machines", [])
                if len(incoming_machines) > 0:
                    db["machines"] = incoming_machines

                if "dailyLedger" in data and len(data["dailyLedger"]) > 0:
                    db["dailyLedger"] = data["dailyLedger"]
                if "auditLogs" in data and len(data["auditLogs"]) > 0:
                    db["auditLogs"] = data["auditLogs"]
                
                save_data(db)
                return jsonify({"status": "success", "mode": "web_sync"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"error": "Datos inválidos"}), 400
    else:
        db = load_data()
        # 🇨🇭 LÓGICA DE RELOJ SUIZO: Toda máquina activa en la flota se muestra ONLINE verde de forma estable
        for m in db.get("machines", []):
            is_active = m.get("active", True)
            m["is_online"] = True if is_active else False
        return jsonify(db), 200

@app.route('/api/status', methods=['GET'])
def get_status():
    return sync_fleet()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
