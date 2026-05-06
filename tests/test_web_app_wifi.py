# tests/test_web_app_wifi.py
import pytest
from unittest.mock import patch, MagicMock
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
