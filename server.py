from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Base de datos en memoria para las palucheras de TELEMETRIA WINWIN
devices_db = {}

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    data = request.json
    if not data or 'device_id' not in data:
        return jsonify({"error": "Datos inválidos"}), 400
    
    dev_id = data['device_id']
    devices_db[dev_id] = {
        "coins": data.get("coins", 0),
        "wifi": data.get("wifi", -60),
        "status": "online",
        "last_seen": "Reciente"
    }
    return jsonify({"status": "success", "message": "Telemetría guardada"}), 200

@app.route('/api/devices', methods=['GET'])
def get_devices():
    return jsonify(devices_db), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)