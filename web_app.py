import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory

# Flask serves both the static web pages and the JSON API.
# static_folder="static" means /static/* URLs map to the static/ directory.
app = Flask(__name__, static_folder="static")

# Absolute paths resolved at startup so all routes use consistent locations
# regardless of the working directory the process was launched from.
CONFIG_PATH = Path(__file__).parent / "config.json"
SOUNDS_DIR = Path(__file__).parent / "sounds"

ALLOWED_EXTENSIONS = {".wav", ".ogg", ".mp3"}
VALID_GROUPS = {"music", "ambiance", "effects"}

# Human-readable names for the six rune slots, used in library API responses
# so the frontend can say "Rune III" instead of just "slot 2".
RUNE_NAMES = ["Rune I", "Rune II", "Rune III", "Rune IV", "Rune V", "Rune VI"]


def _migrate_config(config):
    """Bring an older config.json up to the current schema without losing data.

    Called every time the config is loaded. Returns True if any change was made
    (so the caller knows whether to write it back to disk).

    Migrations performed:
    - Add button_labels if missing (default "Slot 1" … "Slot 6")
    - Convert music slots that are plain strings into single-item lists
      (the schema changed from string → list to support playlists)
    - Add file_labels dict if missing (maps file path → display name)
    - Rename saved_device_address → known_devices list (old BT format)
    """
    dirty = False
    if "button_labels" not in config:
        config["button_labels"] = [f"Slot {i + 1}" for i in range(6)]
        dirty = True
    for i, slot in enumerate(config["sounds"]["music"]):
        if isinstance(slot, str):
            config["sounds"]["music"][i] = [slot]
            dirty = True
    if "file_labels" not in config:
        config["file_labels"] = {}
        dirty = True
    bt = config.setdefault("bluetooth", {})
    if "saved_device_address" in bt:
        addr = bt.pop("saved_device_address")
        if isinstance(addr, str) and addr:
            bt.setdefault("known_devices", [{"address": addr, "name": "Unknown Speaker"}])
        else:
            bt.setdefault("known_devices", [])
        dirty = True
    return dirty


def load_config():
    """Read config.json, run any necessary migrations, and return the dict.
    If the config was migrated, it is written back to disk immediately so the
    next load sees the updated format."""
    with open(CONFIG_PATH) as f:
        config = json.load(f)
    if _migrate_config(config):
        save_config(config)
    return config


def save_config(config):
    """Write the config dict back to config.json with 2-space indentation."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def available_files(group):
    """Return a sorted list of relative file paths (from project root) for all
    audio files in the given group's sounds sub-directory.
    Example: ["sounds/music/battle.ogg", "sounds/music/tavern.mp3"]"""
    folder = SOUNDS_DIR / group
    if not folder.exists():
        return []
    return sorted(
        str(p.relative_to(SOUNDS_DIR.parent))
        for p in folder.iterdir()
        if p.suffix in ALLOWED_EXTENSIONS
    )


# ── Static page routes ─────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/lore")
def lore_page():
    return send_from_directory("static", "instructions.html")


@app.route("/wifi")
def wifi_setup_page():
    return send_from_directory("static", "wifi.html")


@app.route("/library")
def library_page():
    return send_from_directory("static", "library.html")


# ── Sound file serving ─────────────────────────────────────────────────────────

@app.route("/sounds/<path:filename>")
def serve_sound(filename):
    """Serve audio files from the sounds/ directory for browser preview.

    The sounds/ folder is outside Flask's static_folder, so it doesn't get
    automatic file-serving. This route fills that gap. It's used by the Library
    page's audio player — the browser fetches the file directly and plays it
    locally (not through Bluetooth)."""
    return send_from_directory(str(SOUNDS_DIR), filename)


# ── Config API ─────────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET"])
def get_config():
    """Return the data the Board page needs to render itself:
    - sounds: current slot assignments for all three groups
    - available: all uploaded files per group (for the add-to-slot dropdowns)
    - button_labels: the six rune dome labels shown on the board
    - file_labels: display names for audio files (used to show friendly names in dropdowns)"""
    config = load_config()
    return jsonify({
        "sounds": config["sounds"],
        "available": {g: available_files(g) for g in VALID_GROUPS},
        "button_labels": config["button_labels"],
        "file_labels": config.get("file_labels", {}),
    })


@app.route("/api/config/label/<int:index>", methods=["PUT"])
def update_label(index):
    """Update the display label shown on one of the six rune domes on the board.
    Accepts JSON: {"label": "Epic Battle"}. Labels are capped at 32 characters."""
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


# ── Sound slot assignment API ──────────────────────────────────────────────────

@app.route("/api/sounds/<group>/<int:index>", methods=["PUT"])
def remap_sound(group, index):
    """Assign or clear a sound file for one slot in the ambiance or effects group.
    Accepts JSON: {"path": "sounds/effects/sword.wav"} or {"path": null} to clear."""
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


@app.route("/api/sounds/music/<int:index>", methods=["PUT"])
def remap_music_playlist(index):
    """Assign a playlist (ordered list of file paths) to one of the six music slots.
    Accepts JSON: {"paths": ["sounds/music/a.ogg", "sounds/music/b.ogg"]} or {"paths": null} to clear.
    All paths are validated for existence and extension before saving."""
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


# ── Sound library API ──────────────────────────────────────────────────────────

@app.route("/api/sounds/library/<group>", methods=["GET"])
def sound_library(group):
    """Return a list of all uploaded files for a given group.
    Used by the Board page's add-track dropdowns."""
    if group not in VALID_GROUPS:
        return jsonify({"error": "invalid group"}), 400
    return jsonify({"files": available_files(group)})


@app.route("/api/upload/<group>", methods=["POST"])
def upload_sound(group):
    """Accept a multipart file upload and save it to sounds/<group>/.
    Creates a default file label (filename stem, underscores/hyphens → spaces).
    setdefault ensures an existing manually-set label is never overwritten by re-upload."""
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
    path_str = str(dest.relative_to(SOUNDS_DIR.parent))
    default_label = Path(f.filename).stem.replace("_", " ").replace("-", " ")
    config = load_config()
    config.setdefault("file_labels", {}).setdefault(path_str, default_label)
    save_config(config)
    return jsonify({"ok": True, "path": path_str})


def _build_library(config):
    """Build the full library response for all three groups.

    For each file on disk, determines:
    - label: its friendly display name from file_labels (falls back to filename stem)
    - slots: which rune slots it is currently assigned to, with group and rune name

    Music slots are lists (playlists), so a file can appear in multiple playlists.
    Ambiance and effects slots are single paths, so a file can appear in at most one slot per group.
    Returns: {"music": [...], "ambiance": [...], "effects": [...]}"""
    file_labels = config.get("file_labels", {})
    result = {}
    for group in VALID_GROUPS:
        files = []
        for path_str in available_files(group):
            slots = []
            for idx, slot in enumerate(config["sounds"][group]):
                if group == "music":
                    if isinstance(slot, list) and path_str in slot:
                        slots.append({"group": group, "index": idx, "rune": RUNE_NAMES[idx]})
                else:
                    if slot == path_str:
                        slots.append({"group": group, "index": idx, "rune": RUNE_NAMES[idx]})
            label = file_labels.get(path_str, Path(path_str).stem)
            files.append({"path": path_str, "label": label, "slots": slots})
        result[group] = files
    return result


@app.route("/api/library")
def get_library():
    """Return the full library — all files across all groups with labels and slot assignments.
    Used by the Library page to populate its tabbed file table."""
    config = load_config()
    return jsonify(_build_library(config))


@app.route("/api/library/label", methods=["PUT"])
def update_file_label():
    """Rename a file's display label and cascade the change to any rune slot that
    was showing the old label.

    Accepts JSON: {"path": "sounds/music/foo.ogg", "label": "Epic Battle"}

    Cascade logic: if a button_label exactly matches the old file label, it is
    updated to the new one. This keeps the board in sync when a file is renamed
    from the library. Custom labels that don't match (e.g. the user typed something
    different) are left alone."""
    data = request.get_json(silent=True)
    if not data or "path" not in data or "label" not in data:
        return jsonify({"error": "missing path or label"}), 400
    path = data["path"]
    new_label = str(data["label"]).strip()
    if not new_label:
        return jsonify({"error": "label cannot be empty"}), 400
    config = load_config()
    old_label = config.get("file_labels", {}).get(path)
    config.setdefault("file_labels", {})[path] = new_label
    updated_slots = []
    if old_label:
        for idx, lbl in enumerate(config["button_labels"]):
            if lbl == old_label:
                config["button_labels"][idx] = new_label
                updated_slots.append(idx)
    save_config(config)
    return jsonify({"ok": True, "updated_slots": updated_slots})


@app.route("/api/library/file", methods=["DELETE"])
def delete_library_file():
    """Delete an audio file from disk and clean up all references to it.

    Path is passed as a query parameter (?path=sounds/music/foo.ogg).
    After deleting the file:
    - Music slots: remove the path from the playlist array; set slot to null if the playlist becomes empty
    - Ambiance/effects slots: set to null if they reference the deleted file
    - file_labels: remove the entry for this file
    Returns the list of slots that were cleared so the frontend can update its display."""
    path_str = request.args.get("path")
    if not path_str:
        return jsonify({"error": "missing path query parameter"}), 400
    # Construct the absolute path by joining SOUNDS_DIR.parent (project root) with the
    # relative path from config (e.g. "sounds/music/foo.ogg")
    file_path = SOUNDS_DIR.parent / path_str
    if not file_path.exists():
        return jsonify({"error": "file not found"}), 404
    file_path.unlink()
    config = load_config()
    cleared_slots = []
    for group in VALID_GROUPS:
        for idx, slot in enumerate(config["sounds"][group]):
            if group == "music":
                if isinstance(slot, list) and path_str in slot:
                    slot.remove(path_str)
                    if not slot:
                        config["sounds"][group][idx] = None
                    cleared_slots.append({"group": group, "index": idx})
            else:
                if slot == path_str:
                    config["sounds"][group][idx] = None
                    cleared_slots.append({"group": group, "index": idx})
    config.get("file_labels", {}).pop(path_str, None)
    save_config(config)
    return jsonify({"ok": True, "cleared_slots": cleared_slots})


# ── Device management API ──────────────────────────────────────────────────────

@app.route("/api/restart", methods=["POST"])
def restart_sound_machine():
    """Restart the sound-machine systemd service (the main.py GPIO/audio process).
    This is separate from the web app — restarting it reloads config and re-connects Bluetooth."""
    result = subprocess.run(
        ["sudo", "systemctl", "restart", "sound-machine"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return jsonify({"error": result.stderr}), 500
    return jsonify({"ok": True})


# ── Bluetooth API ──────────────────────────────────────────────────────────────

@app.route("/api/bluetooth/known")
def bluetooth_known():
    """Return the list of saved Bluetooth speakers from config.json.
    Each entry has 'address' (MAC) and 'name'."""
    config = load_config()
    return jsonify(config["bluetooth"].get("known_devices", []))


def _parse_bt_devices(output):
    """Parse bluetoothctl output into a list of {address, name} dicts.
    Handles both scan event lines ('[NEW] Device AA:BB Name') and
    'devices' command output ('Device AA:BB Name').
    Deduplicates by MAC address — keeps the first occurrence."""
    devices = []
    seen = set()
    for line in output.splitlines():
        match = re.search(r'Device ([0-9A-Fa-f:]{17}) (.+)', line)
        if match:
            address = match.group(1).upper()
            name = match.group(2).strip()
            if address not in seen:
                seen.add(address)
                devices.append({"address": address, "name": name})
    return devices


@app.route("/api/bluetooth/scan")
def bluetooth_scan():
    """Run an active Bluetooth scan and return newly discovered devices.

    Opens a persistent bluetoothctl interactive session, sends 'scan on',
    waits for scan_timeout seconds (configurable), then harvests discovered
    devices with 'devices'. Devices already in known_devices are excluded
    from the result so the UI only shows truly new speakers."""
    config = load_config()
    scan_timeout = config["bluetooth"].get("scan_timeout", 10)
    known_addresses = {d["address"] for d in config["bluetooth"].get("known_devices", [])}
    proc = subprocess.Popen(
        ["sudo", "bluetoothctl"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        proc.stdin.write("power on\nscan on\n")
        proc.stdin.flush()
        time.sleep(scan_timeout)
        stdout, _ = proc.communicate(input="devices\nquit\n", timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, _ = proc.communicate()
    except Exception:
        proc.kill()
        raise
    devices = _parse_bt_devices(stdout)
    return jsonify([d for d in devices if d["address"] not in known_addresses])


@app.route("/api/bluetooth/os-devices")
def bluetooth_os_devices():
    """Return Bluetooth devices BlueZ already knows about (cached or connected)
    that aren't in our saved known_devices list.
    Used to pre-populate the pairing UI without requiring a fresh scan."""
    config = load_config()
    known_addresses = {d["address"] for d in config["bluetooth"].get("known_devices", [])}
    result = subprocess.run(
        ["sudo", "bluetoothctl", "devices"],
        capture_output=True, text=True,
    )
    devices = _parse_bt_devices(result.stdout)
    return jsonify([d for d in devices if d["address"] not in known_addresses])


def _route_audio_to_bt(address):
    """Switch PulseAudio's output to a Bluetooth speaker by MAC address.

    PulseAudio names BT sinks with underscores instead of colons in the MAC,
    e.g. F4:4E:FD:1B:D4:97 → bluez_sink.F4_4E_FD_1B_D4_97.a2dp_sink.

    Steps:
    1. Activate A2DP (high-quality stereo) profile on the BT audio card
    2. Set that sink as the system-wide default output
    3. Move any streams already playing to the new sink (handles audio that
       started before the BT connection was established)"""
    sanitized = address.replace(":", "_")
    pactl = ["sudo", "pactl", "--server", "unix:/run/user/1000/pulse/native"]
    sink = f"bluez_sink.{sanitized}.a2dp_sink"
    subprocess.run(pactl + ["set-card-profile", f"bluez_card.{sanitized}", "a2dp_sink"],
                   capture_output=True, text=True)
    subprocess.run(pactl + ["set-default-sink", sink], capture_output=True, text=True)
    result = subprocess.run(pactl + ["list", "sink-inputs", "short"],
                            capture_output=True, text=True)
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts:
            subprocess.run(pactl + ["move-sink-input", parts[0], sink],
                           capture_output=True, text=True)


@app.route("/api/bluetooth/pair", methods=["POST"])
def bluetooth_pair():
    """Pair, trust, and connect a new Bluetooth speaker, then save it to config.

    Accepts JSON: {"address": "AA:BB:CC:DD:EE:FF", "name": "My Speaker"}

    The pairing handshake runs as three sequential blocking calls:
    1. pair   — exchanges cryptographic keys with the device
    2. trust  — marks the device so it auto-connects in future sessions
    3. connect — establishes the audio connection

    If connect succeeds, PulseAudio is immediately routed to the new speaker."""
    data = request.get_json(silent=True)
    if not data or "address" not in data or "name" not in data:
        return jsonify({"error": "missing address or name"}), 400
    address = data["address"]
    name = data["name"]
    config = load_config()
    known = config["bluetooth"].setdefault("known_devices", [])
    if not any(d["address"] == address for d in known):
        known.append({"address": address, "name": name})
        save_config(config)
    try:
        subprocess.run(
            ["sudo", "bluetoothctl", "pair", address],
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        pass  # already paired or device slow — still attempt connect
    subprocess.run(
        ["sudo", "bluetoothctl", "trust", address],
        capture_output=True, text=True, timeout=5,
    )
    try:
        result = subprocess.run(
            ["sudo", "bluetoothctl", "connect", address],
            capture_output=True, text=True, timeout=15,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"ok": True, "connected": False})
    connected = (
        "Connection successful" in result.stdout
        or "Already connected" in result.stdout
        or "Connected: yes" in result.stdout
    )
    if connected:
        _route_audio_to_bt(address)
    return jsonify({"ok": True, "connected": connected})


@app.route("/api/bluetooth/device/<address>", methods=["DELETE"])
def bluetooth_forget(address):
    """Remove a saved Bluetooth speaker from config and unpair it from the OS.
    After deletion the device will no longer auto-connect on startup."""
    config = load_config()
    known = config["bluetooth"].get("known_devices", [])
    updated = [d for d in known if d["address"] != address]
    if len(updated) == len(known):
        return jsonify({"error": "not found"}), 404
    config["bluetooth"]["known_devices"] = updated
    save_config(config)
    # Disconnect first so the OS doesn't leave a dangling active connection,
    # then remove so BlueZ forgets the device entirely.
    subprocess.run(["sudo", "bluetoothctl", "disconnect", address], capture_output=True, text=True)
    subprocess.run(["sudo", "bluetoothctl", "remove", address], capture_output=True, text=True)
    return jsonify({"ok": True})


# ── Wi-Fi API ──────────────────────────────────────────────────────────────────

@app.route("/api/wifi/status")
def wifi_status():
    """Return the currently connected Wi-Fi SSID, or null if not connected.
    Uses nmcli in terse mode (-t) to get machine-readable output."""
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "ACTIVE,SSID", "device", "wifi"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split(":", 1)
        if len(parts) == 2 and parts[0] == "yes":
            return jsonify({"ssid": parts[1].replace("\\:", ":")})
    return jsonify({"ssid": None})


def _parse_wifi_scan(stdout):
    """Parse nmcli Wi-Fi scan output into a sorted list of network dicts.

    nmcli -t -f SSID,SIGNAL,SECURITY output uses colons as field separators
    but also escapes literal colons in SSIDs as \:. We rsplit from the right
    to correctly handle SSIDs containing colons.

    Returns networks sorted by signal strength (strongest first), deduplicated by SSID."""
    networks = []
    seen = set()
    for line in stdout.strip().splitlines():
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
    return networks


@app.route("/api/wifi/scan")
def wifi_scan():
    """Return available Wi-Fi networks sorted by signal strength.

    Tries a forced rescan first (--rescan yes) for fresh results. Falls back
    to NetworkManager's cached scan list if the forced scan fails or returns
    nothing (which happens in hotspot mode or when the adapter is busy)."""
    result = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "yes"],
        capture_output=True, text=True,
    )
    networks = _parse_wifi_scan(result.stdout)
    if not networks:
        result = subprocess.run(
            ["sudo", "nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY", "device", "wifi", "list"],
            capture_output=True, text=True,
        )
        networks = _parse_wifi_scan(result.stdout)
    return jsonify(networks)


def _schedule_reboot():
    """Trigger a system reboot 2 seconds from now via a background thread.
    The delay gives the HTTP response time to reach the client before the
    network interface disappears."""
    threading.Timer(2.0, lambda: subprocess.run(["sudo", "systemctl", "reboot"])).start()


@app.route("/api/wifi/connect", methods=["POST"])
def wifi_connect():
    """Connect to a Wi-Fi network and reboot the Pi to apply the new connection.

    Accepts JSON: {"ssid": "MyNetwork", "password": "secret"} (password optional for open networks).

    Before creating the new connection profile:
    1. Delete any existing profiles with the same SSID — stale profiles can have
       a mismatched key-mgmt setting that causes 'property is missing' errors.
    2. Explicitly set key-mgmt (wpa-psk vs none) rather than relying on nmcli to
       infer it from its scan cache — inference fails on 5 GHz or uncached APs.

    Schedules a reboot after success so the new network is used for all services."""
    data = request.get_json(silent=True)
    if not data or "ssid" not in data:
        return jsonify({"error": "missing ssid"}), 400
    ssid = data["ssid"]
    password = data.get("password", "")
    # Find and delete stale profiles by matching on the 802-11-WIRELESS.SSID field value,
    # not the connection name — the name may differ from the SSID for old saved connections.
    lookup = subprocess.run(
        ["sudo", "nmcli", "-t", "-f", "UUID,802-11-WIRELESS.SSID", "connection", "show"],
        capture_output=True, text=True,
    )
    for line in lookup.stdout.strip().splitlines():
        parts = line.split(":", 1)
        if len(parts) == 2 and parts[1].replace("\\:", ":") == ssid:
            subprocess.run(["sudo", "nmcli", "connection", "delete", "uuid", parts[0]],
                           capture_output=True, text=True)
    add_cmd = ["sudo", "nmcli", "connection", "add", "type", "wifi",
               "con-name", ssid, "ssid", ssid, "connection.autoconnect", "yes"]
    if password:
        add_cmd += ["802-11-wireless-security.key-mgmt", "wpa-psk",
                    "802-11-wireless-security.psk", password]
    add_result = subprocess.run(add_cmd, capture_output=True, text=True)
    if add_result.returncode != 0:
        return jsonify({"error": add_result.stderr or add_result.stdout or "nmcli failed"}), 500
    try:
        result = subprocess.run(
            ["sudo", "nmcli", "connection", "up", "id", ssid],
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return jsonify({"error": "nmcli timed out — connection attempt failed"}), 500
    if result.returncode != 0:
        return jsonify({"error": result.stderr or result.stdout or "nmcli failed"}), 500
    _schedule_reboot()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
