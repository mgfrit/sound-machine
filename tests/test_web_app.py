import json
import pytest
from unittest.mock import patch
import web_app


@pytest.fixture
def tmp_config(tmp_path, monkeypatch):
    config = {
        "groups": ["music", "ambiance", "effects"],
        "sounds": {
            "music": ["sounds/music/a.ogg", None, None, None, None, None],
            "ambiance": [None, None, None, None, None, None],
            "effects": [None, None, None, None, None, None],
        },
        "gpio": {
            "group_buttons": [22, 27, 17],
            "sound_buttons": [13, 6, 5, 16, 26, 19],
            "bluetooth_button": 23,
            "bluetooth_hold_time": 2.0,
            "button_bounce_time": 0.05,
        },
        "system_sounds": {"bt_connected": "sounds/system/bt.wav"},
        "bluetooth": {"saved_device_address": None, "scan_timeout": 10},
        "audio": {"music_volume": 0.8, "ambiance_volume": 0.7,
                  "effects_volume": 1.0, "system_sound_volume": 1.0},
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


# ── Migration ────────────────────────────────────────────────────────────────

def test_migrate_adds_button_labels(tmp_config):
    loaded = web_app.load_config()
    assert loaded["button_labels"] == [
        "Slot 1", "Slot 2", "Slot 3", "Slot 4", "Slot 5", "Slot 6"
    ]
    saved = json.loads(tmp_config.read_text())
    assert "button_labels" in saved


def test_migrate_wraps_music_strings(tmp_config):
    loaded = web_app.load_config()
    assert loaded["sounds"]["music"][0] == ["sounds/music/a.ogg"]
    assert loaded["sounds"]["music"][1] is None


def test_migrate_is_idempotent(tmp_config):
    web_app.load_config()
    loaded2 = web_app.load_config()
    assert loaded2["button_labels"] == [
        "Slot 1", "Slot 2", "Slot 3", "Slot 4", "Slot 5", "Slot 6"
    ]


def test_get_config_includes_button_labels(client):
    resp = client.get("/api/config")
    data = resp.get_json()
    assert "button_labels" in data
    assert len(data["button_labels"]) == 6


def test_get_config_music_slots_are_arrays(client):
    resp = client.get("/api/config")
    data = resp.get_json()
    assert data["sounds"]["music"][0] == ["sounds/music/a.ogg"]
    assert data["sounds"]["music"][1] is None


# ── PUT /api/config/label/<index> ────────────────────────────────────────────

def test_put_label_updates_config(client, tmp_config):
    resp = client.put("/api/config/label/0", json={"label": "Battle Theme"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"
    saved = json.loads(tmp_config.read_text())
    assert saved["button_labels"][0] == "Battle Theme"


def test_put_label_invalid_index_returns_400(client):
    resp = client.put("/api/config/label/6", json={"label": "X"})
    assert resp.status_code == 400


def test_put_label_empty_string_returns_400(client):
    resp = client.put("/api/config/label/0", json={"label": ""})
    assert resp.status_code == 400


def test_put_label_missing_field_returns_400(client):
    resp = client.put("/api/config/label/0", json={})
    assert resp.status_code == 400


# ── PUT /api/sounds/music/<index> ────────────────────────────────────────────

def test_put_music_playlist_saves_paths(client, tmp_config, monkeypatch):
    monkeypatch.setattr(web_app.Path, "exists", lambda self: True)
    resp = client.put(
        "/api/sounds/music/0",
        json={"paths": ["sounds/music/a.ogg", "sounds/music/b.ogg"]},
    )
    assert resp.status_code == 200
    saved = json.loads(tmp_config.read_text())
    assert saved["sounds"]["music"][0] == ["sounds/music/a.ogg", "sounds/music/b.ogg"]


def test_put_music_playlist_null_clears_slot(client, tmp_config):
    resp = client.put("/api/sounds/music/0", json={"paths": None})
    assert resp.status_code == 200
    saved = json.loads(tmp_config.read_text())
    assert saved["sounds"]["music"][0] is None


def test_put_music_playlist_invalid_index_returns_400(client):
    resp = client.put("/api/sounds/music/6", json={"paths": None})
    assert resp.status_code == 400


def test_put_music_playlist_missing_field_returns_400(client):
    resp = client.put("/api/sounds/music/0", json={})
    assert resp.status_code == 400


def test_put_music_playlist_nonexistent_file_returns_400(client):
    resp = client.put(
        "/api/sounds/music/0",
        json={"paths": ["sounds/music/ghost.ogg"]},
    )
    assert resp.status_code == 400


# ── GET /api/sounds/library/<group> ──────────────────────────────────────────

def test_get_library_returns_files(client, tmp_path, monkeypatch):
    music_dir = tmp_path / "sounds" / "music"
    music_dir.mkdir(parents=True)
    (music_dir / "track.ogg").touch()
    monkeypatch.setattr(web_app, "SOUNDS_DIR", tmp_path / "sounds")
    resp = client.get("/api/sounds/library/music")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "files" in data
    assert any("track.ogg" in f for f in data["files"])


def test_get_library_invalid_group_returns_400(client):
    resp = client.get("/api/sounds/library/invalid")
    assert resp.status_code == 400
