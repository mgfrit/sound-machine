# WiFi Provisioning via AP Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow the Pi to be connected to a new WiFi network without terminal access — by falling back to a WiFi hotspot when no known network is available, and serving a network-picker page through the existing Flask web app.

**Architecture:** A new systemd service (`wifi-setup.service`) runs a bash script on boot that polls `wlan0` for an IP for 30 seconds; if none appears it uses `nmcli` to activate a hotspot named "SoundMachine-Setup". The existing Flask web app gains three routes: a scan endpoint (calls `nmcli device wifi list`), a connect endpoint (calls `nmcli device wifi connect`, then schedules a reboot), and a static HTML provisioning page. On successful connect the Pi reboots and joins the new network normally.

**Tech Stack:** Python 3 / Flask, `nmcli` (NetworkManager CLI, pre-installed on Pi OS Bookworm), bash, systemd

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `tests/test_web_app_wifi.py` | Create | Tests for all three new Flask routes |
| `web_app.py` | Modify | Add `/wifi`, `/api/wifi/scan`, `/api/wifi/connect` routes |
| `static/wifi.html` | Create | Standalone provisioning UI (scan → pick → enter password → connect) |
| `wifi_setup.sh` | Create | Boot script: polls wlan0, activates hotspot on timeout |
| `wifi-setup.service` | Create | Systemd unit wrapping `wifi_setup.sh` |

---

## Task 1: Test scaffold for WiFi Flask routes

**Files:**
- Create: `tests/test_web_app_wifi.py`

- [ ] **Step 1: Create the test file with a Flask test client fixture**

```python
# tests/test_web_app_wifi.py
import pytest
from unittest.mock import patch, MagicMock
import web_app


@pytest.fixture
def client():
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c
```

- [ ] **Step 2: Run the file to confirm the fixture imports without errors**

```bash
cd /home/admin/sound-machine
venv/bin/pytest tests/test_web_app_wifi.py -v
```

Expected: "no tests ran" (0 collected) — no errors.

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_app_wifi.py
git commit -m "test: add test scaffold for wifi flask routes"
```

---

## Task 2: `/api/wifi/scan` route (TDD)

**Files:**
- Modify: `tests/test_web_app_wifi.py`
- Modify: `web_app.py`

- [ ] **Step 1: Write failing tests for the scan route**

Append to `tests/test_web_app_wifi.py`:

```python
def test_wifi_scan_returns_networks(client):
    mock_result = MagicMock()
    mock_result.stdout = "HomeNetwork:75:WPA2\nCoffeeShop:60:--\n"
    mock_result.returncode = 0
    with patch("web_app.subprocess.run", return_value=mock_result):
        resp = client.get("/api/wifi/scan")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0]["ssid"] == "HomeNetwork"
    assert data[0]["signal"] == 75
    assert data[0]["security"] == "WPA2"


def test_wifi_scan_sorts_by_signal_descending(client):
    mock_result = MagicMock()
    mock_result.stdout = "Weak:30:WPA2\nStrong:90:WPA2\nMid:60:WPA2\n"
    mock_result.returncode = 0
    with patch("web_app.subprocess.run", return_value=mock_result):
        resp = client.get("/api/wifi/scan")
    data = resp.get_json()
    assert [n["ssid"] for n in data] == ["Strong", "Mid", "Weak"]


def test_wifi_scan_deduplicates_ssids(client):
    mock_result = MagicMock()
    mock_result.stdout = "HomeNetwork:75:WPA2\nHomeNetwork:70:WPA2\n"
    mock_result.returncode = 0
    with patch("web_app.subprocess.run", return_value=mock_result):
        resp = client.get("/api/wifi/scan")
    data = resp.get_json()
    assert len(data) == 1


def test_wifi_scan_excludes_empty_ssids(client):
    mock_result = MagicMock()
    mock_result.stdout = ":75:WPA2\nHomeNetwork:60:WPA2\n"
    mock_result.returncode = 0
    with patch("web_app.subprocess.run", return_value=mock_result):
        resp = client.get("/api/wifi/scan")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["ssid"] == "HomeNetwork"


def test_wifi_scan_handles_ssid_with_colon(client):
    mock_result = MagicMock()
    # nmcli escapes colons in SSID values as \:
    mock_result.stdout = "My\\:Network:80:WPA2\n"
    mock_result.returncode = 0
    with patch("web_app.subprocess.run", return_value=mock_result):
        resp = client.get("/api/wifi/scan")
    data = resp.get_json()
    assert data[0]["ssid"] == "My:Network"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
venv/bin/pytest tests/test_web_app_wifi.py -v
```

Expected: 5 failures with "404 NOT FOUND" or "no attribute" errors.

- [ ] **Step 3: Implement the scan route in `web_app.py`**

Add this import at the top of `web_app.py` (if not already present — `subprocess` is already imported):

```python
# no new import needed — subprocess already imported
```

Add this route to `web_app.py` before the `if __name__ == "__main__":` line:

```python
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
venv/bin/pytest tests/test_web_app_wifi.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tests/test_web_app_wifi.py web_app.py
git commit -m "feat: add /api/wifi/scan route"
```

---

## Task 3: `/api/wifi/connect` route (TDD)

**Files:**
- Modify: `tests/test_web_app_wifi.py`
- Modify: `web_app.py`

- [ ] **Step 1: Write failing tests for the connect route**

Append to `tests/test_web_app_wifi.py`:

```python
def test_wifi_connect_success_calls_nmcli_and_reboots(client):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    with patch("web_app.subprocess.run", return_value=mock_result) as mock_run, \
         patch("web_app._schedule_reboot") as mock_reboot:
        resp = client.post("/api/wifi/connect", json={"ssid": "HomeNetwork", "password": "secret"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    mock_run.assert_called_once_with(
        ["nmcli", "device", "wifi", "connect", "HomeNetwork", "password", "secret"],
        capture_output=True, text=True, timeout=30,
    )
    mock_reboot.assert_called_once()


def test_wifi_connect_open_network_omits_password(client):
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    with patch("web_app.subprocess.run", return_value=mock_result) as mock_run, \
         patch("web_app._schedule_reboot"):
        resp = client.post("/api/wifi/connect", json={"ssid": "OpenNetwork"})
    assert resp.status_code == 200
    mock_run.assert_called_once_with(
        ["nmcli", "device", "wifi", "connect", "OpenNetwork"],
        capture_output=True, text=True, timeout=30,
    )


def test_wifi_connect_wrong_password_returns_error(client):
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Error: Connection activation failed."
    mock_result.stdout = ""
    with patch("web_app.subprocess.run", return_value=mock_result), \
         patch("web_app._schedule_reboot") as mock_reboot:
        resp = client.post("/api/wifi/connect", json={"ssid": "HomeNetwork", "password": "wrong"})
    assert resp.status_code == 500
    assert "error" in resp.get_json()
    mock_reboot.assert_not_called()


def test_wifi_connect_missing_ssid_returns_400(client):
    resp = client.post("/api/wifi/connect", json={"password": "secret"})
    assert resp.status_code == 400


def test_wifi_connect_no_json_returns_400(client):
    resp = client.post("/api/wifi/connect")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
venv/bin/pytest tests/test_web_app_wifi.py -v
```

Expected: 5 new failures (the earlier 5 still pass).

- [ ] **Step 3: Add `_schedule_reboot` helper and the connect route to `web_app.py`**

Add this import at the top of `web_app.py` (after existing imports):

```python
import threading
```

Add these two functions to `web_app.py` before the `if __name__ == "__main__":` line:

```python
def _schedule_reboot():
    threading.Timer(2.0, lambda: subprocess.run(["sudo", "systemctl", "reboot"])).start()


@app.route("/api/wifi/connect", methods=["POST"])
def wifi_connect():
    data = request.get_json()
    if not data or "ssid" not in data:
        return jsonify({"error": "missing ssid"}), 400
    ssid = data["ssid"]
    password = data.get("password", "")
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if password:
        cmd += ["password", password]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return jsonify({"error": result.stderr or result.stdout}), 500
    _schedule_reboot()
    return jsonify({"ok": True})
```

- [ ] **Step 4: Run all wifi tests to confirm they pass**

```bash
venv/bin/pytest tests/test_web_app_wifi.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

```bash
venv/bin/pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/test_web_app_wifi.py web_app.py
git commit -m "feat: add /api/wifi/connect route"
```

---

## Task 4: WiFi provisioning HTML page + `/wifi` route

**Files:**
- Create: `static/wifi.html`
- Modify: `web_app.py`

- [ ] **Step 1: Create `static/wifi.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sound Machine — WiFi Setup</title>
  <style>
    body { font-family: sans-serif; max-width: 480px; margin: 40px auto; padding: 0 16px; background: #1a1a2e; color: #eee; }
    h1 { font-size: 1.4rem; margin-bottom: 24px; }
    button { background: #4a4e8a; color: #fff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 1rem; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    ul { list-style: none; padding: 0; margin-top: 16px; }
    li { padding: 10px 12px; margin: 4px 0; background: #2a2a4a; border-radius: 6px; cursor: pointer; display: flex; justify-content: space-between; align-items: center; }
    li.selected { background: #4a4e8a; }
    li:hover:not(.selected) { background: #32325a; }
    .signal { color: #aaa; font-size: 0.85rem; white-space: nowrap; margin-left: 12px; }
    input[type=password] { width: 100%; padding: 10px; margin: 14px 0 10px; border-radius: 6px; border: 1px solid #555; background: #2a2a4a; color: #eee; font-size: 1rem; box-sizing: border-box; }
    #connectForm { margin-top: 12px; }
    #status { margin-top: 16px; padding: 10px 14px; border-radius: 6px; display: none; }
    #status.error { background: #5a1a1a; }
    #status.success { background: #1a5a2a; }
  </style>
</head>
<body>
  <h1>WiFi Setup</h1>
  <button id="scanBtn" onclick="scan()">Scan for networks</button>
  <ul id="networkList"></ul>

  <div id="connectForm" style="display:none">
    <input type="password" id="password" placeholder="Password (leave blank for open networks)">
    <button id="connectBtn" onclick="connect()">Connect &amp; Reboot</button>
  </div>

  <div id="status"></div>

  <script>
    let selectedSSID = null;

    async function scan() {
      const btn = document.getElementById('scanBtn');
      const list = document.getElementById('networkList');
      btn.disabled = true;
      btn.textContent = 'Scanning…';
      list.innerHTML = '';
      document.getElementById('connectForm').style.display = 'none';
      selectedSSID = null;

      try {
        const resp = await fetch('/api/wifi/scan');
        const networks = await resp.json();
        if (networks.length === 0) {
          list.innerHTML = '<li style="cursor:default">No networks found — try scanning again.</li>';
        } else {
          networks.forEach(n => {
            const li = document.createElement('li');
            const lock = (n.security && n.security !== '--') ? '🔒 ' : '';
            li.innerHTML = `<span>${n.ssid}</span><span class="signal">${lock}${n.signal}%</span>`;
            li.onclick = () => selectNetwork(n.ssid, li);
            list.appendChild(li);
          });
        }
      } catch (e) {
        showStatus('Scan failed: ' + e.message, true);
      }

      btn.disabled = false;
      btn.textContent = 'Scan for networks';
    }

    function selectNetwork(ssid, el) {
      document.querySelectorAll('#networkList li').forEach(li => li.classList.remove('selected'));
      el.classList.add('selected');
      selectedSSID = ssid;
      document.getElementById('connectForm').style.display = 'block';
      document.getElementById('password').focus();
    }

    async function connect() {
      if (!selectedSSID) return;
      const btn = document.getElementById('connectBtn');
      const password = document.getElementById('password').value;
      btn.disabled = true;
      btn.textContent = 'Connecting…';

      try {
        const resp = await fetch('/api/wifi/connect', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ssid: selectedSSID, password }),
        });
        const data = await resp.json();
        if (data.ok) {
          showStatus('Connected! Rebooting in a few seconds…', false);
        } else {
          showStatus('Failed: ' + (data.error || 'Unknown error'), true);
          btn.disabled = false;
          btn.textContent = 'Connect & Reboot';
        }
      } catch (e) {
        showStatus('Error: ' + e.message, true);
        btn.disabled = false;
        btn.textContent = 'Connect & Reboot';
      }
    }

    function showStatus(msg, isError) {
      const el = document.getElementById('status');
      el.textContent = msg;
      el.className = isError ? 'error' : 'success';
      el.style.display = 'block';
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Add the `/wifi` route to `web_app.py`**

Add this route near the existing `index` route:

```python
@app.route("/wifi")
def wifi_setup_page():
    return send_from_directory("static", "wifi.html")
```

- [ ] **Step 3: Run the full test suite**

```bash
venv/bin/pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add static/wifi.html web_app.py
git commit -m "feat: add wifi provisioning page and /wifi route"
```

---

## Task 5: Boot script `wifi_setup.sh`

**Files:**
- Create: `wifi_setup.sh`

- [ ] **Step 1: Create `wifi_setup.sh`**

```bash
#!/bin/bash
# Waits up to 30s for wlan0 to get an IP. If none, activates a WiFi hotspot
# so the user can configure a new network via the web UI at 192.168.4.1:5000/wifi.

SSID="SoundMachine-Setup"
PASSWORD="soundmachine1"

for i in $(seq 1 30); do
    if ip addr show wlan0 2>/dev/null | grep -q "inet "; then
        echo "wlan0 connected — skipping hotspot setup."
        exit 0
    fi
    sleep 1
done

echo "No WiFi connection after 30s — activating hotspot '$SSID'."
nmcli device wifi hotspot ifname wlan0 ssid "$SSID" password "$PASSWORD"
echo "Hotspot active. Connect to '$SSID' and open 192.168.4.1:5000/wifi"
exit 0
```

- [ ] **Step 2: Make it executable**

```bash
chmod +x wifi_setup.sh
```

- [ ] **Step 3: Manual smoke test — connected case**

With the Pi on its normal WiFi:

```bash
sudo ./wifi_setup.sh
```

Expected output: `wlan0 connected — skipping hotspot setup.`

- [ ] **Step 4: Commit**

```bash
git add wifi_setup.sh
git commit -m "feat: add wifi_setup.sh boot script"
```

---

## Task 6: Systemd service, sudoers, and installation

**Files:**
- Create: `wifi-setup.service`

- [ ] **Step 1: Create `wifi-setup.service`**

```ini
[Unit]
Description=WiFi Setup AP Fallback
After=NetworkManager.service
Before=sound-machine-web.service
Wants=NetworkManager.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/home/admin/sound-machine/wifi_setup.sh
User=root

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Update sudoers to allow `systemctl reboot`**

Check the existing sudoers entry (the `/api/restart` route already uses `sudo systemctl restart`):

```bash
sudo cat /etc/sudoers.d/sound-machine 2>/dev/null || sudo grep -r sound-machine /etc/sudoers*
```

If a file like `/etc/sudoers.d/sound-machine` exists, add `systemctl reboot` to it. If not, create it:

```bash
sudo tee /etc/sudoers.d/sound-machine > /dev/null << 'EOF'
admin ALL=(ALL) NOPASSWD: /usr/bin/systemctl restart sound-machine
admin ALL=(ALL) NOPASSWD: /usr/bin/systemctl reboot
EOF
sudo chmod 440 /etc/sudoers.d/sound-machine
```

Verify the file is valid:

```bash
sudo visudo -c
```

Expected: `parsed OK`

- [ ] **Step 3: Install and enable the service on the Pi**

```bash
sudo cp wifi-setup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wifi-setup.service
```

- [ ] **Step 4: Verify the service is enabled**

```bash
sudo systemctl is-enabled wifi-setup.service
```

Expected: `enabled`

- [ ] **Step 5: Test the full boot flow (manual)**

Temporarily disable a known WiFi network (or move the Pi somewhere without coverage), then reboot:

```bash
sudo reboot
```

After reboot:
1. Check that "SoundMachine-Setup" appears in your phone's WiFi list
2. Connect to it (password: `soundmachine1`)
3. Open a browser to `192.168.4.1:5000/wifi`
4. Click "Scan for networks", pick a network, enter credentials, click "Connect & Reboot"
5. After reboot, confirm the Pi connected to the target network: `ip addr show wlan0`

- [ ] **Step 6: Commit**

```bash
git add wifi-setup.service
git commit -m "feat: add wifi-setup systemd service and installation instructions"
```
