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
    data = request.json
    if not data:
        return jsonify({"error": "Datos inválidos o JSON vacío"}), 400

    # Capturar tanto device_id como mac para compatibilidad con el ESP32
    dev_id = data.get('device_id') or data.get('mac')
    if not dev_id:
        return jsonify({"error": "Falta device_id o mac en el payload"}), 400

    coins_received = data.get('coins', 0)
    wifi_signal = data.get('wifi', -60)
    prize_status = data.get('prize', '')

    db = load_data()

    # Si la máquina no está en la base de datos, la creamos con los datos de tu terreno
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

    # Cada pulso del billetero equivale exactamente a 100 CLP
    if coins_received > 0:
        monto_clp = coins_received * 100
        db[dev_id]["box_cash"] += monto_clp
        db[dev_id]["daily_sales"] += monto_clp

    # Registro de premios si el ESP32 indica dispensación
    if prize_status == "dispense":
        db[dev_id]["prizes"] += 1

    db[dev_id]["wifi"] = wifi_signal
    db[dev_id]["status"] = "online"

    save_data(db)

    print(f"✅ [SERVIDOR] Máquina {dev_id} actualizada: +{coins_received * 100} CLP | Caja Box Total: {db[dev_id]['box_cash']} CLP")

    return jsonify({
        "status": "success",
        "active": db[dev_id]["active"],
        "box_cash": db[dev_id]["box_cash"],
        "daily_sales": db[dev_id]["daily_sales"]
    }), 200

# Ruta para que el panel web (index.html) consulte los montos en tiempo real
@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify(load_data()), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
