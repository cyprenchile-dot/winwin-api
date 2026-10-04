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
                    # Si el archivo tiene datos válidos, los devolvemos
                    if len(data.get("machines", [])) > 0:
                        return data
                    # Si el archivo existe pero está vacío, revisamos si hay respaldo previo en memoria
                    return data
        except Exception as e:
            print(f"⚠️ Error leyendo JSON persistente: {e}")
    
    # Si el archivo no existe por primera vez, creamos el default
    if not os.path.exists(DATABASE_FILE):
        save_data(DEFAULT_DATABASE)
    return DEFAULT_DATABASE

def save_data(data):
    try:
        # PROTECCIÓN ABSOLUTA: Nunca guardar un archivo completamente vacío si ya existían máquinas
        if os.path.exists(DATABASE_FILE):
            with open(DATABASE_FILE, 'r') as f:
                existing_data = json.load(f)
                if len(existing_data.get("machines", [])) > 0 and len(data.get("machines", [])) == 0:
                    print("🚨 ALTA SEGURIDAD: Se bloqueó un intento de sobrescribir el disco con una flota vacía.")
                    return # Rechaza la escritura destructiva

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
                incoming_machines = data.get("machines", [])
                
                # ESCUDO ANTI-BORRADO ABSOLUTO EN SERVIDOR
                if len(incoming_machines) == 0 and len(db.get("machines", [])) > 0:
                    return jsonify({"status": "protected", "message": "Acción bloqueada: Intento de sobrescribir flota con array vacío"}), 200

                db["machines"] = incoming_machines
                if "dailyLedger" in data and len(data["dailyLedger"]) > 0:
                    db["dailyLedger"] = data["dailyLedger"]
                if "auditLogs" in data and len(data["auditLogs"]) > 0:
                    db["auditLogs"] = data["auditLogs"]
                
                save_data(db)
                return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"error": "Datos inválidos"}), 400
    else:
        db = load_data()
        current_time = time.time()
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
