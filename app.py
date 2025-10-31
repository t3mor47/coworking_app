from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_cors import CORS
from datetime import datetime
import json
import os
import uuid

app = Flask(__name__)
app.secret_key = "super_secret_key"
CORS(app)

# ---------- НАСТРОЙКИ ----------
QUEUE_FILE = "queue.json"
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "default_password")  # задаётся через Render
OPEN_HOUR = 11
CLOSE_HOUR = 23

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ----------
def load_queue():
    if os.path.exists(QUEUE_FILE):
        try:
            with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_queue(q):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)

def get_position(device_id):
    for i, person in enumerate(queue):
        if person["device_id"] == device_id:
            return i + 1
    return 0

def is_queue_open():
    now = datetime.now().hour
    return OPEN_HOUR <= now < CLOSE_HOUR

# ---------- ГЛОБАЛЬНАЯ ОЧЕРЕДЬ ----------
queue = [p for p in load_queue() if "device_id" in p and p["device_id"]]

# ---------- СТРАНИЦЫ ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_page"))
    return render_template("admin_dashboard.html")

# ---------- API ----------
@app.route("/api/join", methods=["POST"])
def api_join():
    global queue
    data = request.get_json()
    name = data.get("name", "").strip()
    code = data.get("code", "").strip()
    device_id = data.get("device_id")

    # Если device_id не передан — генерируем новый
    if not device_id:
        device_id = str(uuid.uuid4())

    # Проверяем, открыта ли очередь
    if not is_queue_open():
        return jsonify({"error": "closed", "message": "Queue open from 11:00 to 23:00"}), 403

    if not name or not code:
        return jsonify({"error": "missing", "message": "Missing name or code"}), 400

    # Уже в очереди?
    for p in queue:
        if p["device_id"] == device_id:
            pos = get_position(device_id)
            return jsonify({"position": pos, "message": "Already in queue", "device_id": device_id})

    # Добавляем нового участника
    queue.append({"name": name, "code": code, "device_id": device_id})
    save_queue(queue)
    pos = len(queue)
    return jsonify({"position": pos, "device_id": device_id})

@app.route("/api/status/<device_id>")
def api_status(device_id):
    pos = get_position(device_id)
    if pos > 0:
        return jsonify({"in_queue": True, "position": pos})
    return jsonify({"in_queue": False, "position": 0})

@app.route("/api/admin/login", methods=["POST"])
def api_admin_login():
    data = request.get_json()
    password = data.get("password", "")
    if password == ADMIN_PASSWORD:
        session["admin_logged_in"] = True
        return jsonify({"status": "ok"})
    return jsonify({"error": "wrong_password"}), 401

@app.route("/api/admin/queue")
def api_admin_queue():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "unauthorized"}), 403
    return jsonify(queue)

@app.route("/api/admin/remove", methods=["POST"])
def api_admin_remove():
    if not session.get("admin_logged_in"):
        return jsonify({"error": "unauthorized"}), 403

    global queue
    data = request.get_json()
    device_id = data.get("device_id")
    if not device_id:
        return jsonify({"error": "missing device_id"}), 400

    queue = [p for p in queue if p["device_id"] != device_id]
    save_queue(queue)
    return jsonify({"status": "ok"})

# ---------- АЛИАСЫ ДЛЯ СОВМЕСТИМОСТИ С index.html ----------
@app.route("/join", methods=["POST"])
def join_alias():
    return api_join()

@app.route("/position", methods=["POST"])
def position_alias():
    data = request.get_json()
    name = data.get("name", "").strip()
    code = data.get("code", "").strip()
    if not name or not code:
        return jsonify({"position": 0})

    device_id = f"{name}_{code}"
    pos = get_position(device_id)
    if pos > 0:
        return jsonify({"position": pos})
    return jsonify({"position": 0})

# ---------- СТАРТ ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050)
