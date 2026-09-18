from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Estado centralizado de la flota en la nube de Render
fleet_state = {
    "machines": [],
    "dailyLedger": []
}

@app.route('/api/telemetry', methods=['GET', 'POST'])
def handle_telemetry():
    global fleet_state
    if request.method == 'POST':
        data = request.get_json()
        if data:
            device_id = data.get('device_id')
            coins = data.get('coins', 0)
            prize = data.get('prize', '')

            # Buscar si la máquina ya existe en la flota
            machine = next((m for m in fleet_state["machines"] if m["mac"] == device_id), None)
            if not machine:
                # Si es un dispositivo nuevo, se registra automáticamente
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

            # Actualizar valores si la máquina está activa
            if machine.get("active", True):
                if coins > 0:
                    machine["sales"] += coins * 100
                    machine["box"] += coins * 100
                if prize and prize != "":
                    machine["prizes"] = machine.get("prizes", 0) + 1
            
            # Actualizar señal Wi-Fi
            if 'wifi' in data:
                machine["wifi"] = data['wifi']

            return jsonify({'success': True, 'message': 'Sincronizado en la nube'}), 200
        return jsonify({'success': False}), 400
    else:
        # Devuelve el estado completo de la flota a cualquier cliente conectado
        return jsonify(fleet_state), 200

# Endpoint para sincronizar cambios de administración (agregar, eliminar, pausar, vaciar cajas)
@app.route('/api/sync-fleet', methods=['GET', 'POST'])
def sync_fleet():
    global fleet_state
    if request.method == 'POST':
        data = request.get_json()
        if data:
            if "machines" in data:
                fleet_state["machines"] = data["machines"]
            if "dailyLedger" in data:
                fleet_state["dailyLedger"] = data["dailyLedger"]
            return jsonify({'success': True}), 200
        return jsonify({'success': False}), 400
    else:
        return jsonify(fleet_state), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
