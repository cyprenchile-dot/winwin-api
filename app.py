from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Almacenamiento temporal en memoria para la flota
telemetry_logs = []

@app.route('/api/telemetry', methods=['GET', 'POST'])
def handle_telemetry():
    if request.method == 'POST':
        data = request.get_json()
        if data:
            telemetry_logs.append(data)
            if len(telemetry_logs) > 100:
                telemetry_logs.pop(0)  # Mantener los últimos 100 registros
            return jsonify({
                'success': True,
                'message': '¡Enviado a Render y sincronizado en Netlify!'
            }), 200
        return jsonify({'success': False}), 400
    else:
        # Petición GET: entrega los registros al panel web
        return jsonify(telemetry_logs), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
