from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

telemetry_logs = []

@app.route('/api/telemetry', methods=['GET', 'POST'])
def handle_telemetry():
    if request.method == 'POST':
        data = request.get_json()
        if data:
            telemetry_logs.append(data)
            if len(telemetry_logs) > 100:
                telemetry_logs.pop(0)
            return jsonify({'success': True, 'message': 'Registrado'}), 200
        return jsonify({'success': False}), 400
    else:
        # Envía los registros pendientes y limpia la lista para el siguiente ciclo
        current_logs = telemetry_logs.copy()
        telemetry_logs.clear()
        return jsonify(current_logs), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
