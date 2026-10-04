from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

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

# 🇨🇭 RUTA OFICIAL ESP32: Sincronización atómica de Acumulado y Venta Diaria
@app.route('/api/telemetry', methods=['POST'])
def receive_esp32_telemetry():
    try:
        data = request.get_json(force=True)
        if data and isinstance(data, dict) and "mac" in data:
            db = load_data()
            mac = data.get("mac")
            new_coins = int(data.get("coins", 0))
            wifi_rssi = int(data.get("wifi", -50))
            current_t = time.time()
            
            # Obtener la fecha local exacta de Chile
            try:
                today_str = datetime.now(ZoneInfo("America/Santiago")).strftime('%Y-%m-%d')
            except Exception:
                today_str = datetime.now().strftime('%Y-%m-%d')
            
            machine_found = False
            for m in db.get("machines", []):
                if m.get("mac") == mac:
                    machine_found = True
                    # 1. Actualizar acumulado total de ventas
                    current_sales = m.get("sales", 0)
                    m["sales"] = current_sales + (new_coins * 100)
                    
                    # 2. Actualizar estado de red y latido
                    m["wifi"] = wifi_rssi
                    m["last_seen"] = current_t
                    m["is_online"] = True
                    
                    # 3. Sumar estrictamente al registro del día actual
                    if "dailyLogs" not in m or not isinstance(m["dailyLogs"], dict):
                        m["dailyLogs"] = {}
                    current_day_sales = m["dailyLogs"].get(today_str, 0)
                    m["dailyLogs"][today_str] = current_day_sales + (new_coins * 100)
            
            if not machine_found:
                new_m = {
                    "mac": mac,
                    "name": f"Terminal {mac[-5:]}",
                    "location": "Local Terreno",
                    "sales": new_coins * 100,
                    "wifi": wifi_rssi,
                    "prizes": 0,
                    "active": True,
                    "is_online": True,
                    "last_seen": current_t,
                    "coinInitial": 3768,
                    "dailyLogs": {today_str: new_coins * 100},
                    "withdrawalHistory": []
                }
                db["machines"].append(new_m)
            
            save_data(db)
            return jsonify({"status": "success", "message": "Telemetry received"}), 200
        return jsonify({"error": "Invalid payload"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    if request.method == 'POST':
        try:
            data = request.get_json(force=True)
            if data and isinstance(data, dict):
                db = load_data()
                incoming_machines = data.get("machines", [])
                if len(incoming_machines) > 0:
                    for incoming in incoming_machines:
                        for existing in db.get("machines", []):
                            if existing.get("mac") == incoming.get("mac"):
                                # Preservar last_seen del servidor
                                if "last_seen" in existing:
                                    incoming["last_seen"] = existing["last_seen"]
                    
                    # 🇨🇭 Aceptamos directamente los datos limpios de la web (permitiendo reseteos a $0)
                    db["machines"] = incoming_machines

                if "dailyLedger" in data and len(data["dailyLedger"]) > 0:
                    db["dailyLedger"] = data["dailyLedger"]
                if "auditLogs" in data and len(data["auditLogs"]) > 0:
                    db["auditLogs"] = data["auditLogs"]
                
                save_data(db)
                return jsonify({"status": "success"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 400
        return jsonify({"error": "Invalid payload"}), 400
    else:
        db = load_data()
        current_time = time.time()
        for m in db.get("machines", []):
            last_seen = m.get("last_seen", 0)
            # Detección rápida de desconexión (45 segundos)
            if last_seen > 0 and (current_time - last_seen) <= 45:
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
