# tests/test_web_app_wifi.py
import pytest
from unittest.mock import patch, MagicMock, call
import web_app


@pytest.fixture
def client():
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


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


def test_wifi_connect_success_calls_nmcli_and_reboots(client):
    lookup = MagicMock(stdout="abc-123:HomeNetwork\ndef-456:OtherNet\n", returncode=0)
    delete = MagicMock(returncode=0)
    add    = MagicMock(returncode=0, stderr="")
    up     = MagicMock(returncode=0, stderr="")
    with patch("web_app.subprocess.run", side_effect=[lookup, delete, add, up]) as mock_run, \
         patch("web_app._schedule_reboot") as mock_reboot:
        resp = client.post("/api/wifi/connect", json={"ssid": "HomeNetwork", "password": "secret"})
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    mock_run.assert_has_calls([
        call(["sudo", "nmcli", "-t", "-f", "UUID,802-11-WIRELESS.SSID", "connection", "show"],
             capture_output=True, text=True),
        call(["sudo", "nmcli", "connection", "delete", "uuid", "abc-123"],
             capture_output=True, text=True),
        call(["sudo", "nmcli", "connection", "add", "type", "wifi",
              "con-name", "HomeNetwork", "ssid", "HomeNetwork", "connection.autoconnect", "yes",
              "802-11-wireless-security.key-mgmt", "wpa-psk",
              "802-11-wireless-security.psk", "secret"],
             capture_output=True, text=True),
        call(["sudo", "nmcli", "connection", "up", "id", "HomeNetwork"],
             capture_output=True, text=True, timeout=30),
    ])
    mock_reboot.assert_called_once()


def test_wifi_connect_open_network_omits_password(client):
    lookup = MagicMock(stdout="", returncode=0)
    add    = MagicMock(returncode=0, stderr="")
    up     = MagicMock(returncode=0, stderr="")
    with patch("web_app.subprocess.run", side_effect=[lookup, add, up]) as mock_run, \
         patch("web_app._schedule_reboot"):
        resp = client.post("/api/wifi/connect", json={"ssid": "OpenNetwork"})
    assert resp.status_code == 200
    mock_run.assert_has_calls([
        call(["sudo", "nmcli", "connection", "add", "type", "wifi",
              "con-name", "OpenNetwork", "ssid", "OpenNetwork", "connection.autoconnect", "yes"],
             capture_output=True, text=True),
        call(["sudo", "nmcli", "connection", "up", "id", "OpenNetwork"],
             capture_output=True, text=True, timeout=30),
    ])


def test_wifi_connect_wrong_password_returns_error(client):
    lookup = MagicMock(stdout="", returncode=0)
    add    = MagicMock(returncode=0, stderr="")
    up     = MagicMock(returncode=1, stderr="Error: Connection activation failed.", stdout="")
    with patch("web_app.subprocess.run", side_effect=[lookup, add, up]), \
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
