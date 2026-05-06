# WiFi Provisioning via AP Fallback Mode

**Date:** 2026-05-06  
**Status:** Approved

## Problem

The Pi cannot join a new WiFi network without terminal access. When taken to a new location, the only recourse is SSH — which requires being on the same network first (catch-22).

## Solution

If the Pi boots and fails to connect to a known WiFi network within 30 seconds, it activates a WiFi hotspot ("SoundMachine-Setup"). The existing Flask web app then serves a `/wifi` provisioning page at `192.168.4.1:5000/wifi`. The user connects to the hotspot, scans for networks, picks one, enters credentials, and the Pi connects and reboots. On reboot it joins the new network and resumes normal operation.

Bluetooth audio is unaffected — it runs on `hci0`, a separate OS interface from `wlan0`.

## Architecture

```
Boot
 └─ wifi-setup.service  (runs as root, before sound-machine-web.service)
     ├─ poll wlan0 for IP (up to 30s)
     ├─ [IP found]     → exit 0, normal boot
     └─ [timeout]      → nmcli hotspot on wlan0
                          SSID: SoundMachine-Setup
                          Password: soundmachine1
                          Flask /wifi page becomes accessible at 192.168.4.1:5000
```

## Components

### `wifi-setup.service` (new)

- Runs as root (needs nmcli and ip access)
- `RemainAfterExit=yes` so systemd considers it "active" while hotspot is up
- Ordered: `After=NetworkManager.service`, `Before=sound-machine-web.service`
- Implemented as a short bash script (`wifi_setup.sh`)

**wifi_setup.sh logic:**
```
for i in 0..29:
    if wlan0 has an IP → exit 0
    sleep 1
nmcli device wifi hotspot ifname wlan0 ssid SoundMachine-Setup password soundmachine1
# script exits here; NetworkManager owns the hotspot independently
# RemainAfterExit=yes marks the service active so dependents start correctly
```

### Flask routes (added to `web_app.py`)

| Route | Method | Description |
|---|---|---|
| `/wifi` | GET | Serves the provisioning HTML page |
| `/api/wifi/scan` | GET | Returns JSON list of visible networks |
| `/api/wifi/connect` | POST | Connects to chosen network, then reboots |

**`GET /api/wifi/scan`** — runs:
```
nmcli -t -f SSID,SIGNAL,SECURITY device wifi list --rescan yes
```
Returns `[{ssid, signal, security}, ...]`, deduplicated, sorted by signal strength descending. Strips empty SSIDs (hidden networks).

**`POST /api/wifi/connect`** — accepts `{ssid, password}`:
1. Runs `nmcli device wifi connect <ssid> password <password>`
2. Waits up to 15s polling for wlan0 IP (confirms success)
3. On success: calls `systemctl reboot`
4. On failure (wrong password / timeout): returns `{error: "..."}` — no reboot

### Static page (`static/wifi.html`) (new)

Standalone HTML page (not part of the existing sound machine SPA). Contains:
- "Scan for networks" button
- List of scanned networks (SSID, signal bars, lock icon if secured)
- Password input field (shown after selecting a network)
- "Connect & Reboot" button
- Status/error message area

Minimal styling consistent with the existing UI. No framework dependencies.

## Error Handling

| Scenario | Behaviour |
|---|---|
| Wrong password | `nmcli` exits non-zero → API returns error → page shows message, no reboot |
| Scan returns empty | Page shows "No networks found" with a Retry button |
| User reboots before connecting | Pi falls back to hotspot again on next boot |
| Pi connects mid-session (unlikely race) | `wifi-setup.service` has already exited cleanly; hotspot was never started |

## Security

- Hotspot password (`soundmachine1`) prevents random passers-by from accessing the config page, while being simple enough to type on a phone
- The `/wifi` and `/api/wifi/*` routes are always registered but only reachable when on the hotspot network (or the local WiFi) — no additional auth needed
- `systemctl reboot` requires the Flask process to have passwordless sudo for that command (or run as root) — already precedented by the existing `/api/restart` route using `sudo systemctl restart sound-machine`

## Upgrade Path

Adding a captive portal later is purely additive:
1. Install `dnsmasq`, configure it to resolve all DNS to `192.168.4.1` (active only in hotspot mode)
2. Add one `iptables` rule redirecting port 80 → 5000

No changes to Option A components required.

## Files Changed

| File | Change |
|---|---|
| `wifi_setup.sh` | New — boot script that polls for WiFi and activates hotspot |
| `wifi-setup.service` | New — systemd unit wrapping `wifi_setup.sh` |
| `web_app.py` | Add `/wifi`, `/api/wifi/scan`, `/api/wifi/connect` routes |
| `static/wifi.html` | New — standalone provisioning page |
