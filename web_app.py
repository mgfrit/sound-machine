import json
import os
import subprocess
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

CONFIG_PATH = Path(__file__).parent / "config.json"
SOUNDS_DIR = Path(__file__).parent / "sounds"
ALLOWED_EXTENSIONS = {".wav", ".ogg", ".mp3"}
VALID_GROUPS = {"music", "ambiance", "effects"}


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


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


@app.route("/api/config", methods=["GET"])
def get_config():
    config = load_config()
    return jsonify({
        "sounds": config["sounds"],
        "available": {g: available_files(g) for g in VALID_GROUPS},
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
