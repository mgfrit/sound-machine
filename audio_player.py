import pygame

class AudioPlayer:
    MUSIC_CH = 0
    AMBIANCE_CH = 1

    def __init__(self, volumes):
        pygame.mixer.init(frequency=44100, channels=2, buffer=512)
        pygame.mixer.set_num_channels(8)
        self._volumes = volumes
        self._music_ch = pygame.mixer.Channel(self.MUSIC_CH)
        self._ambiance_ch = pygame.mixer.Channel(self.AMBIANCE_CH)

    def play_music(self, path):
        if path is None:
            return
        self._music_ch.stop()
        sound = pygame.mixer.Sound(path)
        sound.set_volume(self._volumes["music"])
        self._music_ch.play(sound, loops=-1)

    def play_ambiance(self, path):
        if path is None:
            return
        self._ambiance_ch.stop()
        sound = pygame.mixer.Sound(path)
        sound.set_volume(self._volumes["ambiance"])
        self._ambiance_ch.play(sound, loops=-1)

    def play_effect(self, path):
        if path is None:
            return
        sound = pygame.mixer.Sound(path)
        sound.set_volume(self._volumes["effects"])
        ch = pygame.mixer.find_channel(force=True)
        ch.play(sound)

    def play_system_sound(self, path):
        if path is None:
            return
        sound = pygame.mixer.Sound(path)
        ch = pygame.mixer.find_channel(force=True)
        ch.play(sound)

    def stop_music(self):
        self._music_ch.fadeout(2000)

    def stop_ambiance(self):
        self._ambiance_ch.fadeout(2000)
