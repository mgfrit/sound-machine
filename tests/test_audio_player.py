import pytest
from unittest.mock import MagicMock
import audio_player

@pytest.fixture(autouse=True)
def mock_pygame(monkeypatch):
    mock = MagicMock()
    monkeypatch.setattr(audio_player, 'pygame', mock)
    return mock

def test_play_music_playlist_plays_first_track(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.play_music_playlist(["sounds/music/a.ogg", "sounds/music/b.ogg"])
    mock_pygame.mixer.music.load.assert_called_with("sounds/music/a.ogg")
    mock_pygame.mixer.music.play.assert_called_once()


def test_play_music_playlist_registers_end_event(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.play_music_playlist(["sounds/music/a.ogg"])
    mock_pygame.mixer.music.set_endevent.assert_called_once()


def test_play_music_playlist_empty_list_does_nothing(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.play_music_playlist([])
    assert not mock_pygame.mixer.music.load.called


def test_advance_playlist_loads_next_track(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.play_music_playlist(["sounds/music/a.ogg", "sounds/music/b.ogg"])
    mock_pygame.mixer.music.load.reset_mock()
    player.advance_playlist()
    mock_pygame.mixer.music.load.assert_called_with("sounds/music/b.ogg")


def test_advance_playlist_wraps_to_first_track(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.play_music_playlist(["sounds/music/a.ogg"])
    mock_pygame.mixer.music.load.reset_mock()
    player.advance_playlist()
    mock_pygame.mixer.music.load.assert_called_with("sounds/music/a.ogg")


def test_advance_playlist_does_nothing_when_empty(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.advance_playlist()
    assert not mock_pygame.mixer.music.load.called

def test_play_ambiance_stops_previous_track(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0})
    player.play_ambiance("sounds/ambiance/a.ogg")
    player.play_ambiance("sounds/ambiance/b.ogg")
    assert mock_pygame.mixer.Channel.return_value.stop.called

def test_play_effect_loads_sound(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0})
    player.play_effect("sounds/effects/boom.wav")
    mock_pygame.mixer.Sound.assert_called_with("sounds/effects/boom.wav")

def test_stop_music_fades_out(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.stop_music()
    mock_pygame.mixer.music.fadeout.assert_called_with(2000)


def test_stop_music_clears_playlist(mock_pygame):
    player = audio_player.AudioPlayer({"music_volume": 0.8, "ambiance_volume": 0.7, "effects_volume": 1.0, "system_sound_volume": 1.0})
    player.play_music_playlist(["sounds/music/a.ogg", "sounds/music/b.ogg"])
    player.stop_music()
    assert player._playlist == []
    assert player._playlist_index == 0
