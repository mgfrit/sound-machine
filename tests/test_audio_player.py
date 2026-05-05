import pytest
from unittest.mock import MagicMock, patch
import audio_player

@pytest.fixture(autouse=True)
def mock_pygame(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(audio_player, 'pygame', mock)
    return mock

def test_play_music_stops_previous_track(mock_pygame):
    player = audio_player.AudioPlayer({"music": 0.8, "ambiance": 0.7, "effects": 1.0})
    player.play_music("sounds/music/track1.ogg")
    player.play_music("sounds/music/track2.ogg")
    assert mock_pygame.mixer.Channel.return_value.stop.called

def test_play_ambiance_stops_previous_track(mock_pygame):
    player = audio_player.AudioPlayer({"music": 0.8, "ambiance": 0.7, "effects": 1.0})
    player.play_ambiance("sounds/ambiance/a.ogg")
    player.play_ambiance("sounds/ambiance/b.ogg")
    assert mock_pygame.mixer.Channel.return_value.stop.called

def test_play_effect_loads_sound(mock_pygame):
    player = audio_player.AudioPlayer({"music": 0.8, "ambiance": 0.7, "effects": 1.0})
    player.play_effect("sounds/effects/boom.wav")
    mock_pygame.mixer.Sound.assert_called_with("sounds/effects/boom.wav")

def test_stop_music_fades_out(mock_pygame):
    player = audio_player.AudioPlayer({"music": 0.8, "ambiance": 0.7, "effects": 1.0})
    player.stop_music()
    mock_pygame.mixer.Channel.return_value.fadeout.assert_called_with(2000)

def test_none_path_is_ignored(mock_pygame):
    player = audio_player.AudioPlayer({"music": 0.8, "ambiance": 0.7, "effects": 1.0})
    player.play_music(None)
    assert not mock_pygame.mixer.Sound.called
