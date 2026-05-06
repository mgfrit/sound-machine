import json
import os
import subprocess
import threading
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

CONFIG_PATH = Path(__file__).parent / "config.json"
SOUNDS_DIR = Path(__file__).parent / "sounds"
ALLOWED_EXTENSIONS = {".wav", ".ogg", ".mp3"}
VALID_GROUPS = {"music", "ambiance", "effects"}


def _migrate_config(config):
    """Ensure button_labels exists and music slots are arrays. Returns True if config changed."""
    dirty = False
    if "button_labels" not in config:
        config["button_labels"] = [f"Slot {i + 1}" for i in range(6)]
        dirty = True
    for i, slot in enumerate(config["sounds"]["music"]):
        if isinstance(slot, str):
            config["sounds"]["music"][i] = [slot]
            dirty = True
    return dirty


def load_config():
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    if _migrate_config(config):
        save_config(config)
    return config


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def available_files(group):
    folder = SOUNDS_DIR / group
    if not folder.exists():
        return []
    return sorted(
        str(p.relative_to(SOUNDS_DIR.parent))
        for p in folder.iterdir()
        if p.suffix in ALLOWED_EXTENSIONS
    )


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/lore")
def lore_page():
    return send_from_directory("static", "instructions.html")


@app.route("/wifi")
def wifi_setup_page():
    return send_from_directory("static", "wifi.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    config = load_config()
    return jsonify({
        "sounds": config["sounds"],
        "available": {g: available_files(g) for g in VALID_GROUPS},
        "button_labels": config["button_labels"],
    })


@app.route("/api/sounds/<group>/<int:index>", methods=["PUT"])
def remap_sound(group, index):
    if group not in VALID_GROUPS:
        return jsonify({"error": "invalid group"}), 400
    data = request.get_json()
    if data is None or "path" not in data:
        return jsonify({"error": "missing 'path' field"}), 400
    path = data["path"]
    if path is not None and not Path(path).exists():
        return jsonify({"error": f"file not found: {path}"}), 400
    config = load_config()
    if index < 0 or index >= len(config["sounds"][group]):
        return jsonify({"error": "index out of range"}), 400
    config["sounds"][group][index] = path
    save_config(config)
    return jsonify({"ok": True})


@app.route("/api/config/label/<int:index>", methods=["PUT"])
def update_label(index):
    if index < 0 or index > 5:
        return jsonify({"error": "index out of range"}), 400
    data = request.get_json(silent=True)
    if not data or "label" not in data:
        return jsonify({"error": "missing 'label' field"}), 400
    label = str(data["label"]).strip()
    if not label:
        return jsonify({"error": "label cannot be empty"}), 400
    config = load_config()
    config["button_labels"][index] = label[:32]
    save_config(config)
    return jsonify({"status": "ok"})


@app.route("/api/sounds/music/<int:index>", methods=["PUT"])
def remap_music_playlist(index):
    if index < 0 or index > 5:
        return jsonify({"error": "index out of range"}), 400
    data = request.get_json(silent=True)
    if data is None or "paths" not in data:
        return jsonify({"error": "missing 'paths' field"}), 400
    paths = data["paths"]
    if paths is not None:
        if not isinstance(paths, list):
            return jsonify({"error": "'paths' must be a list or null"}), 400
        for p in paths:
            if Path(p).suffix.lower() not in ALLOWED_EXTENSIONS:
                return jsonify({"error": f"unsupported format: {p}"}), 400
            if not Path(p).exists():
                return jsonify({"error": f"file not found: {p}"}), 400
    config = load_config()
    config["sounds"]["music"][index] = paths
    save_config(config)
    return jsonify({"status": "ok"})


@app.route("/api/sounds/library/<group>", methods=["GET"])
def sound_library(group):
    if group not in VALID_GROUPS:
        return jsonify({"error": "invalid group"}), 400
    return jsonify({"files": available_files(group)})


@app.route("/api/upload/<group>", methods=["POST"])
def upload_sound(group):
    if group not in VALID_GROUPS:
        return jsonify({"error": "invalid group"}), 400
    if "file" not in request.files:
        return jsonify({"error": "no file in request"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400
    ext = Path(f.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"unsupported format — use {ALLOWED_EXTENSIONS}"}), 400
    dest = SOUNDS_DIR / group / Path(f.filename).name
    f.save(dest)
    return jsonify({"ok": True, "path": str(dest.relative_to(SOUNDS_DIR.parent))})


@app.route("/api/restart", methods=["POST"])
def restart_sound_machine():
    result = subprocess.run(
        ["sudo", "systemctl", "restart", "sound-machine"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return jsonify({"error": result.stderr}), 500
    return jsonify({"ok": True})


@app.route("/api/wifi/scan")
def wifi_scan():
    result = subprocess.run(
        ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
        capture_output=True, text=True,
    )
    networks = []
    seen = set()
    for line in result.stdout.strip().splitlines():
        # Split from right so colons in SSID (escaped as \: by nmcli) are handled
        parts = line.rsplit(":", 2)
        if len(parts) != 3:
            continue
        ssid = parts[0].replace("\\:", ":")
        signal_raw, security = parts[1], parts[2]
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        networks.append({
            "ssid": ssid,
            "signal": int(signal_raw) if signal_raw.isdigit() else 0,
            "security": security,
        })
    networks.sort(key=lambda n: n["signal"], reverse=True)
    return jsonify(networks)


def _schedule_reboot():
    threading.Timer(2.0, lambda: subprocess.run(["sudo", "systemctl", "reboot"])).start()


@app.route("/api/wifi/connect", methods=["POST"])
def wifi_connect():
    data = request.get_json(silent=True)
    if not data or "ssid" not in data:
        return jsonify({"error": "missing ssid"}), 400
    ssid = data["ssid"]
    password = data.get("password", "")
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return jsonify({"error": "nmcli timed out — connection attempt failed"}), 500
    if result.returncode != 0:
        return jsonify({"error": result.stderr or result.stdout or "nmcli failed"}), 500
    _schedule_reboot()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
