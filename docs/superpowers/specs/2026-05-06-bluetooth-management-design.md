# Bluetooth Management Redesign

**Date:** 2026-05-06  
**Status:** Approved

## Problem

The current Bluetooth setup has three problems:
1. A physical button (GPIO 23) triggers re-pairing — this button is being removed from the hardware.
2. If the saved device is unavailable, the Pi pairs to the first random Bluetooth device it finds — this is undesirable.
3. The Pi can only remember one device; the user has no way to manage devices without editing config directly.

## Solution

Remove the button and random pairing. Introduce a list of known devices that the Pi tries on startup (first match wins). Add a Bluetooth management UI to The Weave page (`wifi.html`) so users can scan for nearby speakers, pair them with immediate connection attempt, and forget devices — the same flow as a phone's Bluetooth settings.

## Architecture

```
Boot
 └─ sound-machine.service
     ├─ reset_gpio.py                 (unchanged)
     └─ main.py
         └─ BluetoothManager.initiate(known_devices)
             ├─ try known_devices[0] → connect → play sound, stop
             ├─ try known_devices[1] → connect → play sound, stop
             └─ none found → continue (no scan, no random pairing)

Web UI (sound-machine-web.service → web_app.py)
 └─ GET  /api/bluetooth/known         → list known devices from config
 └─ GET  /api/bluetooth/scan          → scan nearby BT devices
 └─ POST /api/bluetooth/pair          → save + connect + A2DP switch
 └─ DELETE /api/bluetooth/device/<a>  → forget device
```

## Config Change

`saved_device_address` (string) is replaced with `known_devices` (list):

```json
"bluetooth": {
  "known_devices": [
    {"address": "F4:4E:FD:1B:D4:97", "name": "JBL Flip 5"}
  ],
  "scan_timeout": 10
}
```

A migration function (same pattern as `_migrate_config` in `web_app.py`) converts the old field on first load: if `saved_device_address` is a non-empty string, it becomes `known_devices[0]` with name `"Unknown Speaker"` and the old key is removed. If it is `null` or absent, the key is simply removed.

## Components

### `bluetooth_manager.py`

- `initiate(known_devices)` — iterates `known_devices`, calls `_connect` on each address, stops at first success and fires `_on_connected`. `scan_timeout` is no longer a parameter (it is only used by `web_app.py`'s scan endpoint).
- `_run` no longer calls `_scan` or attempts random devices.
- `_save_device` removed — saving is the web layer's responsibility.
- `_scan` and `_parse_scan_output` removed — scanning for the UI is done directly in `web_app.py`.

### `button_handler.py`

- `_bt_button` removed.
- `on_bt_held` parameter removed.
- `__init__` signature becomes `(config, state_machine, audio_player)`.

### `main.py`

- `on_bt_held` callback removed.
- `bt_manager.initiate()` called once on startup with `config["bluetooth"]["known_devices"]`.
- `handler._bt_button.close()` removed from the shutdown handler.

### `sound-machine.service`

- `ExecStartPre=/home/admin/sound-machine/bt-setup.sh` line removed.

### `bt-setup.sh`

- File deleted. Bluetooth connection on boot is now handled by `main.py` → `BluetoothManager`.

### `config.json`

- `gpio.bluetooth_button` key removed.
- `gpio.bluetooth_hold_time` key removed.
- `bluetooth.saved_device_address` replaced by `bluetooth.known_devices`.

### `web_app.py` — new endpoints

**`GET /api/bluetooth/known`**  
Returns `known_devices` list from config.  
Response: `[{"address": "...", "name": "..."}, ...]`

**`GET /api/bluetooth/scan`**  
Runs `sudo bluetoothctl --timeout <scan_timeout> scan on` as a subprocess (same sudo pattern as existing `sudo nmcli` WiFi calls).  
Parses `[NEW] Device <addr> <name>` lines (reuses existing parse pattern from `BluetoothManager`).  
Filters out addresses already in `known_devices`.  
Response: `[{"address": "...", "name": "..."}, ...]`

**`POST /api/bluetooth/pair`**  
Body: `{"address": "...", "name": "..."}`  
Steps:
1. Append to `known_devices` in config (if not already present by address).
2. Run `sudo bluetoothctl connect <address>` (15s timeout).
3. If connected: run `sudo pactl --server unix:/run/user/1000/pulse/native set-card-profile bluez_card.<sanitized_addr> a2dp_sink` (address with `_` instead of `:`).
4. Return `{"ok": true, "connected": true|false}`.

Address sanitization for pactl: replace `:` with `_`.  
Connection failure does not remove the device from `known_devices` — it will retry on next startup.

**`DELETE /api/bluetooth/device/<address>`**  
Removes matching entry from `known_devices` by address.  
Returns `{"ok": true}` or `{"error": "not found"}` with 404.

### `static/wifi.html`

Bluetooth section added **above** the existing WiFi section. The page subtitle updates to "Connect the machine to speakers and networks."

**Bluetooth section layout:**
- Section icon: 🔊, title: "Speaker Binding (Bluetooth)"
- Sub-heading "Bound Speakers" → list of known devices, each with a "Forget" button
- "Scan for Speakers" button (disabled + text changes to "Scanning…" while in progress)
- Sub-heading "Nearby Devices" → appears after scan completes; each entry has a "Pair" button
- Status area below shows result: "✓ Paired and connected.", "Saved — connection failed, will retry on startup.", or error text

**Interaction flow:**
1. Page load: `GET /api/bluetooth/known` → populate Bound Speakers list
2. Scan: `GET /api/bluetooth/scan` → populate Nearby Devices list (already-known addresses excluded)
3. Pair: `POST /api/bluetooth/pair` → on response, move device from Nearby to Bound Speakers list, show status
4. Forget: `DELETE /api/bluetooth/device/<address>` → remove from Bound Speakers list on success

## Error Handling

| Scenario | Behaviour |
|---|---|
| No known devices on startup | BluetoothManager exits cleanly, no sound played |
| Known device out of range on startup | `bluetoothctl connect` fails silently, tries next in list |
| Scan returns no devices | UI shows "No devices found — try scanning again." |
| Pair connect fails | Device still saved; UI shows "Saved — connection failed, will retry on startup." |
| pactl A2DP switch fails | Logged, not fatal — audio may not route correctly until restart |
| Forget non-existent address | API returns 404 |

## Files Changed

| File | Change |
|---|---|
| `config.json` | Replace `saved_device_address` + button GPIO keys with `known_devices` list |
| `bluetooth_manager.py` | Remove scan/random pairing/save; iterate known_devices on startup |
| `button_handler.py` | Remove `_bt_button` and `on_bt_held` parameter |
| `main.py` | Remove button callback; call `initiate(known_devices)` on startup |
| `sound-machine.service` | Remove `ExecStartPre` for `bt-setup.sh` |
| `bt-setup.sh` | Deleted |
| `web_app.py` | Add 4 new `/api/bluetooth/*` endpoints; add config migration |
| `static/wifi.html` | Add Bluetooth section above WiFi section |
