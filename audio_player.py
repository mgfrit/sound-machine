import pygame

MUSIC_END = pygame.USEREVENT + 1


class AudioPlayer:
    AMBIANCE_CH = 1

    def __init__(self, volumes):
        pygame.mixer.init(frequency=44100, channels=2, buffer=512)
        pygame.mixer.set_num_channels(8)
        self._volumes = {
            "music": volumes.get("music_volume", 0.8),
            "ambiance": volumes.get("ambiance_volume", 0.7),
            "effects": volumes.get("effects_volume", 1.0),
            "system": volumes.get("system_sound_volume", 1.0),
        }
        self._ambiance_ch = pygame.mixer.Channel(self.AMBIANCE_CH)
        self._cache = {}
        self._playlist = []
        self._playlist_index = 0

    def preload(self, paths):
        for path in paths:
            if path and path not in self._cache:
                try:
                    self._cache[path] = pygame.mixer.Sound(path)
                    print(f"Preloaded: {path}")
                except Exception as e:
                    print(f"Warning: could not preload {path}: {e}")

    def _load(self, path):
        if path not in self._cache:
            self._cache[path] = pygame.mixer.Sound(path)
        return self._cache[path]

    def play_music_playlist(self, paths):
        if not paths:
            return
        self._playlist = list(paths)
        self._playlist_index = 0
        pygame.mixer.music.set_endevent(MUSIC_END)
        pygame.mixer.music.load(self._playlist[0])
        pygame.mixer.music.set_volume(self._volumes["music"])
        pygame.mixer.music.play(0, fade_ms=0)

    def advance_playlist(self):
        if not self._playlist:
            return
        self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
        pygame.mixer.music.load(self._playlist[self._playlist_index])
        pygame.mixer.music.set_volume(self._volumes["music"])
        pygame.mixer.music.play(0, fade_ms=1500)

    def play_ambiance(self, path):
        if path is None:
            return
        self._ambiance_ch.stop()
        sound = self._load(path)
        sound.set_volume(self._volumes["ambiance"])
        self._ambiance_ch.play(sound, loops=-1)

    def play_effect(self, path):
        if path is None:
            return
        sound = self._load(path)
        sound.set_volume(self._volumes["effects"])
        ch = pygame.mixer.find_channel(force=True)
        ch.play(sound)

    def play_system_sound(self, path):
        if path is None:
            return
        sound = self._load(path)
        sound.set_volume(self._volumes["system"])
        ch = pygame.mixer.find_channel(force=True)
        ch.play(sound)

    def stop_music(self):
        self._playlist = []
        self._playlist_index = 0
        pygame.mixer.music.fadeout(2000)

    def stop_ambiance(self):
        self._ambiance_ch.fadeout(2000)
