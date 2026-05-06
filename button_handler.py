from gpiozero import Button

class ButtonHandler:
    def __init__(self, config, state_machine, audio_player):
        self._sm = state_machine
        self._player = audio_player
        self._sounds = config["sounds"]
        self._active_music = None
        self._active_ambiance = None
        gpio = config["gpio"]

        self._group_buttons = [
            Button(pin, pull_up=True, bounce_time=gpio["button_bounce_time"])
            for pin in gpio["group_buttons"]
        ]
        self._sound_buttons = [
            Button(pin, pull_up=True, bounce_time=gpio["button_bounce_time"])
            for pin in gpio["sound_buttons"]
        ]

        for i, btn in enumerate(self._group_buttons):
            btn.when_pressed = lambda i=i: self._on_group(i)
        for i, btn in enumerate(self._sound_buttons):
            btn.when_pressed = lambda i=i: self._on_sound(i)

    def _on_group(self, index):
        self._sm.select_group(index)

    def _on_sound(self, index):
        result = self._sm.select_sound(index)
        if result is None:
            return
        group, sound_index = result
        group_name = group.name.lower()
        sounds_list = self._sounds.get(group_name, [])
        if sound_index >= len(sounds_list):
            return
        if group_name == "music":
            paths = sounds_list[sound_index]
            if isinstance(paths, str):
                paths = [paths] if paths else None
            if self._active_music == sound_index:
                self._player.stop_music()
                self._active_music = None
            elif paths:
                self._player.play_music_playlist(paths)
                self._active_music = sound_index
        elif group_name == "ambiance":
            path = sounds_list[sound_index]
            if self._active_ambiance == sound_index:
                self._player.stop_ambiance()
                self._active_ambiance = None
            else:
                self._player.play_ambiance(path)
                self._active_ambiance = sound_index
        elif group_name == "effects":
            path = sounds_list[sound_index]
            self._player.play_effect(path)
