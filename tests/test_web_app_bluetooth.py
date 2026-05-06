import json
import pytest
from unittest.mock import patch, MagicMock
import web_app


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    config = {
        "groups": ["music", "ambiance", "effects"],
        "sounds": {
            "music": [None, None, None, None, None, None],
            "ambiance": [None, None, None, None, None, None],
            "effects": [None, None, None, None, None, None],
        },
        "gpio": {
            "group_buttons": [22, 27, 17],
            "sound_buttons": [13, 6, 5, 16, 26, 19],
            "button_bounce_time": 0.05,
        },
        "system_sounds": {},
        "bluetooth": {
            "known_devices": [
                {"address": "AA:BB:CC:DD:EE:FF", "name": "Test Speaker"}
            ],
            "scan_timeout": 5,
        },
        "audio": {
            "music_volume": 0.8, "ambiance_volume": 0.7,
            "effects_volume": 1.0, "system_sound_volume": 1.0,
        },
    }
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(config))
    monkeypatch.setattr(web_app, "CONFIG_PATH", cfg_file)
    return cfg_file


@pytest.fixture
def client(tmp_config):
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        yield c


# ── Migration ─────────────────────────────────────────────────────────────────

def test_migrate_converts_saved_device_address(tmp_path, monkeypatch):
    config = {
        "groups": ["music", "ambiance", "effects"],
        "sounds": {"music": [None]*6, "ambiance": [None]*6, "effects": [None]*6},
        "gpio": {"group_buttons": [22], "sound_buttons": [13], "button_bounce_time": 0.05},
        "system_sounds": {},
        "bluetooth": {"saved_device_address": "F4:4E:FD:1B:D4:97", "scan_timeout": 10},
        "audio": {"music_volume": 0.8, "ambiance_volume": 0.7,
                  "effects_volume": 1.0, "system_sound_volume": 1.0},
    }
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(config))
    monkeypatch.setattr(web_app, "CONFIG_PATH", cfg_file)
    loaded = web_app.load_config()
    assert loaded["bluetooth"]["known_devices"] == [
        {"address": "F4:4E:FD:1B:D4:97", "name": "Unknown Speaker"}
    ]
    assert "saved_device_address" not in loaded["bluetooth"]


def test_migrate_null_saved_device_address(tmp_path, monkeypatch):
    config = {
        "groups": ["music", "ambiance", "effects"],
        "sounds": {"music": [None]*6, "ambiance": [None]*6, "effects": [None]*6},
        "gpio": {"group_buttons": [22], "sound_buttons": [13], "button_bounce_time": 0.05},
        "system_sounds": {},
        "bluetooth": {"saved_device_address": None, "scan_timeout": 10},
        "audio": {"music_volume": 0.8, "ambiance_volume": 0.7,
                  "effects_volume": 1.0, "system_sound_volume": 1.0},
    }
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(config))
    monkeypatch.setattr(web_app, "CONFIG_PATH", cfg_file)
    loaded = web_app.load_config()
    assert loaded["bluetooth"]["known_devices"] == []
    assert "saved_device_address" not in loaded["bluetooth"]


# ── GET /api/bluetooth/known ───────────────────────────────────────────────────

def test_bluetooth_known_returns_list(client):
    resp = client.get("/api/bluetooth/known")
    assert resp.status_code == 200
    assert resp.get_json() == [{"address": "AA:BB:CC:DD:EE:FF", "name": "Test Speaker"}]


def test_bluetooth_known_empty_list(tmp_path, monkeypatch):
    config = {
        "groups": ["music", "ambiance", "effects"],
        "sounds": {"music": [None]*6, "ambiance": [None]*6, "effects": [None]*6},
        "gpio": {"group_buttons": [22], "sound_buttons": [13], "button_bounce_time": 0.05},
        "system_sounds": {},
        "bluetooth": {"known_devices": [], "scan_timeout": 5},
        "audio": {"music_volume": 0.8, "ambiance_volume": 0.7,
                  "effects_volume": 1.0, "system_sound_volume": 1.0},
    }
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(json.dumps(config))
    monkeypatch.setattr(web_app, "CONFIG_PATH", cfg_file)
    web_app.app.config["TESTING"] = True
    with web_app.app.test_client() as c:
        resp = c.get("/api/bluetooth/known")
    assert resp.get_json() == []


# ── GET /api/bluetooth/scan ────────────────────────────────────────────────────

def _bt_scan_patches(stdout):
    """Mock the interactive bluetoothctl Popen session and time.sleep."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = (stdout, "")
    return (
        patch("web_app.subprocess.Popen", return_value=mock_proc),
        patch("web_app.time.sleep"),
    )


def test_bluetooth_scan_returns_nearby_devices(client):
    popen, sleep = _bt_scan_patches(
        "Device 11:22:33:44:55:66 UE Boom 3\n"
        "Device BB:CC:DD:EE:FF:AA Sony Speaker\n"
    )
    with popen, sleep:
        resp = client.get("/api/bluetooth/scan")
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data) == 2
    assert data[0] == {"address": "11:22:33:44:55:66", "name": "UE Boom 3"}
    assert data[1] == {"address": "BB:CC:DD:EE:FF:AA", "name": "Sony Speaker"}


def test_bluetooth_scan_excludes_known_devices(client):
    popen, sleep = _bt_scan_patches(
        "Device AA:BB:CC:DD:EE:FF Test Speaker\n"
        "Device 11:22:33:44:55:66 New Speaker\n"
    )
    with popen, sleep:
        resp = client.get("/api/bluetooth/scan")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["address"] == "11:22:33:44:55:66"


def test_bluetooth_scan_empty_returns_empty_list(client):
    popen, sleep = _bt_scan_patches("")
    with popen, sleep:
        resp = client.get("/api/bluetooth/scan")
    assert resp.get_json() == []


def test_bluetooth_scan_deduplicates_addresses(client):
    popen, sleep = _bt_scan_patches(
        "Device 11:22:33:44:55:66 Speaker\n"
        "Device 11:22:33:44:55:66 Speaker\n"
    )
    with popen, sleep:
        resp = client.get("/api/bluetooth/scan")
    assert len(resp.get_json()) == 1


# ── POST /api/bluetooth/pair ───────────────────────────────────────────────────

def test_bluetooth_pair_saves_and_connects(client, tmp_config):
    connect_result = MagicMock(stdout="Connection successful", returncode=0)
    pactl_result = MagicMock(returncode=0)
    with patch("web_app.subprocess.run", side_effect=[connect_result, pactl_result]):
        resp = client.post("/api/bluetooth/pair",
                           json={"address": "11:22:33:44:55:66", "name": "New Speaker"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["connected"] is True
    saved = json.loads(tmp_config.read_text())
    assert any(d["address"] == "11:22:33:44:55:66"
               for d in saved["bluetooth"]["known_devices"])


def test_bluetooth_pair_saves_even_when_connect_fails(client, tmp_config):
    connect_result = MagicMock(stdout="Failed to connect", returncode=1)
    with patch("web_app.subprocess.run", return_value=connect_result):
        resp = client.post("/api/bluetooth/pair",
                           json={"address": "11:22:33:44:55:66", "name": "New Speaker"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["connected"] is False
    saved = json.loads(tmp_config.read_text())
    assert any(d["address"] == "11:22:33:44:55:66"
               for d in saved["bluetooth"]["known_devices"])


def test_bluetooth_pair_does_not_duplicate_known_device(client, tmp_config):
    connect_result = MagicMock(stdout="Connection successful", returncode=0)
    pactl_result = MagicMock(returncode=0)
    with patch("web_app.subprocess.run", side_effect=[connect_result, pactl_result]):
        client.post("/api/bluetooth/pair",
                    json={"address": "AA:BB:CC:DD:EE:FF", "name": "Test Speaker"})
    saved = json.loads(tmp_config.read_text())
    addresses = [d["address"] for d in saved["bluetooth"]["known_devices"]]
    assert addresses.count("AA:BB:CC:DD:EE:FF") == 1


def test_bluetooth_pair_missing_address_returns_400(client):
    resp = client.post("/api/bluetooth/pair", json={"name": "Speaker"})
    assert resp.status_code == 400


def test_bluetooth_pair_missing_name_returns_400(client):
    resp = client.post("/api/bluetooth/pair", json={"address": "11:22:33:44:55:66"})
    assert resp.status_code == 400


def test_bluetooth_pair_no_json_returns_400(client):
    resp = client.post("/api/bluetooth/pair")
    assert resp.status_code == 400


# ── DELETE /api/bluetooth/device/<address> ─────────────────────────────────────

def test_bluetooth_forget_removes_device(client, tmp_config):
    with patch("web_app.subprocess.run") as mock_run:
        resp = client.delete("/api/bluetooth/device/AA:BB:CC:DD:EE:FF")
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    saved = json.loads(tmp_config.read_text())
    assert not any(d["address"] == "AA:BB:CC:DD:EE:FF"
                   for d in saved["bluetooth"]["known_devices"])
    mock_run.assert_called_once_with(
        ["sudo", "bluetoothctl", "remove", "AA:BB:CC:DD:EE:FF"],
        capture_output=True, text=True,
    )


def test_bluetooth_forget_unknown_address_returns_404(client):
    resp = client.delete("/api/bluetooth/device/FF:FF:FF:FF:FF:FF")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_bluetooth_scan_normalizes_lowercase_mac(client):
    popen, sleep = _bt_scan_patches("Device f4:4e:fd:1b:d4:97 BUGANI M118\n")
    with popen, sleep:
        resp = client.get("/api/bluetooth/scan")
    data = resp.get_json()
    assert len(data) == 1
    assert data[0]["address"] == "F4:4E:FD:1B:D4:97"
    assert data[0]["name"] == "BUGANI M118"
