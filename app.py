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

    try:
        coins_received = int(data.get('coins') or data.get('pulse') or 0)
    except:
        coins_received = 0

    try:
        wifi_signal = int(data.get('wifi', -60))
    except:
        wifi_signal = -60

    prize_status = str(data.get('prize', ''))
    is_active = data.get('active')

    db = load_data()
    if "machines" not in db:
        db["machines"] = []

    machine = None
    for m in db["machines"]:
        if m.get("mac") == dev_id or m.get("device_id") == dev_id:
            machine = m
            break

    # Si la MAC no existe, se crea por única vez con un nombre base
    if not machine:
        machine = {
            "mac": dev_id,
            "device_id": dev_id,
            "name": f"Terminal {dev_id[-5:] if len(dev_id)>=5 else 'Nuevo'}",
            "location": "Local por definir",
            "active": True,
            "box": 0,
            "sales": 0,
            "prizes": 0,
            "wifi": wifi_signal,
            "dailyLogs": {},
            "withdrawalHistory": []
        }
        db["machines"].append(machine)

    # Si ya existe, SOLO actualizamos telemetría, latido y wifi (respetando el nombre y ubicación editados por ti)
    if coins_received > 0:
        monto_clp = coins_received * 100
        machine["box"] = machine.get("box", 0) + monto_clp
        machine["sales"] = machine.get("sales", 0) + monto_clp

    if prize_status == "dispense":
        machine["prizes"] = machine.get("prizes", 0) + 1

    if is_active is not None:
        machine["active"] = bool(is_active)

    machine["wifi"] = wifi_signal

    save_data(db)
    return jsonify({"status": "success", "box": machine["box"], "sales": machine["sales"]}), 200
