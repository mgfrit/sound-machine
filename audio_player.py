import pygame

# Custom pygame event type fired when a music track finishes playing naturally.
# main.py's event loop listens for this and calls advance_playlist() to move to the next track.
MUSIC_END = pygame.USEREVENT + 1


# Wraps pygame's audio system and exposes simple play/stop methods for each sound category.
#
# Audio architecture:
#   Music    — streamed via pygame.mixer.music (one global stream). Music files are too large
#               to hold in memory, so they're loaded on demand and streamed from disk.
#   Ambiance — played on a dedicated mixer channel (channel 1), looping forever until stopped.
#               Using a named channel lets us fade it out independently of everything else.
#   Effects  — played on any available channel, fire-and-forget (no stopping needed).
#   System   — same as effects; used for internal sounds like the Bluetooth connection chime.
class AudioPlayer:
    AMBIANCE_CH = 1  # pygame mixer channel number reserved for ambiance

    def __init__(self, volumes):
        # 44.1 kHz stereo with a small buffer (512 samples ≈ 11 ms) for responsive playback
        pygame.mixer.init(frequency=44100, channels=2, buffer=512)
        pygame.mixer.set_num_channels(8)  # Support up to 8 simultaneous sounds

        # Volume levels for each category, read from config.json's "audio" section (0.0–1.0)
        self._volumes = {
            "music":    volumes.get("music_volume", 0.8),
            "ambiance": volumes.get("ambiance_volume", 0.7),
            "effects":  volumes.get("effects_volume", 1.0),
            "system":   volumes.get("system_sound_volume", 1.0),
        }

        # Reserve channel 1 as the dedicated ambiance channel
        self._ambiance_ch = pygame.mixer.Channel(self.AMBIANCE_CH)

        # In-memory cache: file path → pygame.mixer.Sound object.
        # Avoids re-reading from disk on every button press.
        self._cache = {}

        # Currently active music playlist and position within it
        self._playlist = []
        self._playlist_index = 0

    def preload(self, paths):
        """Load audio files into the cache at startup so they play without delay.
        Only called for ambiance, effects, and system sounds — not music,
        because music files are large and are streamed instead."""
        for path in paths:
            if path and path not in self._cache:
                try:
                    self._cache[path] = pygame.mixer.Sound(path)
                    print(f"Preloaded: {path}")
                except Exception as e:
                    print(f"Warning: could not preload {path}: {e}")

    def _load(self, path):
        """Return a cached Sound object, loading from disk on first access."""
        if path not in self._cache:
            self._cache[path] = pygame.mixer.Sound(path)
        return self._cache[path]

    def play_music_playlist(self, paths):
        """Start playing a list of music tracks from the first track.
        Registers MUSIC_END as the event to fire when each track ends,
        so main.py's loop can call advance_playlist() to move to the next one."""
        if not paths:
            return
        self._playlist = list(paths)
        self._playlist_index = 0
        pygame.mixer.music.set_endevent(MUSIC_END)
        pygame.mixer.music.load(self._playlist[0])
        pygame.mixer.music.set_volume(self._volumes["music"])
        pygame.mixer.music.play(0, fade_ms=0)  # play(0) = play once, not looping

    def advance_playlist(self):
        """Step to the next track, wrapping back to the start after the last one.
        Called by main.py each time a MUSIC_END event is received."""
        if not self._playlist:
            return
        self._playlist_index = (self._playlist_index + 1) % len(self._playlist)
        pygame.mixer.music.load(self._playlist[self._playlist_index])
        pygame.mixer.music.set_volume(self._volumes["music"])
        pygame.mixer.music.play(0, fade_ms=1500)  # 1.5 s crossfade into each new track

    def play_ambiance(self, path):
        """Start looping an ambient sound on the dedicated ambiance channel.
        Stops whatever is currently playing on that channel first.
        loops=-1 means loop indefinitely until explicitly stopped."""
        if path is None:
            return
        self._ambiance_ch.stop()
        sound = self._load(path)
        sound.set_volume(self._volumes["ambiance"])
        self._ambiance_ch.play(sound, loops=-1)

    def play_effect(self, path):
        """Play a one-shot sound effect on any available mixer channel.
        find_channel(force=True) steals the oldest active channel if all 8 are busy."""
        if path is None:
            return
        sound = self._load(path)
        sound.set_volume(self._volumes["effects"])
        ch = pygame.mixer.find_channel(force=True)
        ch.play(sound)

    def play_system_sound(self, path):
        """Play an internal system sound (e.g. Bluetooth connection chime).
        Behaves exactly like an effect: plays once on any free channel."""
        if path is None:
            return
        sound = self._load(path)
        sound.set_volume(self._volumes["system"])
        ch = pygame.mixer.find_channel(force=True)
        ch.play(sound)

    def stop_music(self):
        """Stop music with a 2-second fadeout and clear the playlist."""
        self._playlist = []
        self._playlist_index = 0
        pygame.mixer.music.fadeout(2000)

    def stop_ambiance(self):
        """Fade out the looping ambiance over 2 seconds."""
        self._ambiance_ch.fadeout(2000)
