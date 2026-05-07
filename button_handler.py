from gpiozero import Button


# Wires the physical GPIO buttons to audio actions.
#
# Button layout:
#   Group buttons (top row, 3 buttons): Music | Ambiance | Effects
#   Sound buttons (bottom row, 6 buttons): Rune I | II | III | IV | V | VI
#
# Interaction model:
#   1. Press a group button → selects the active sound category
#   2. Press a rune button  → plays or toggles the sound assigned to that slot
#
# Music and ambiance are toggles: pressing the active rune stops it; pressing a different
# rune switches to that sound. Effects always play once with no toggle behaviour.
class ButtonHandler:
    def __init__(self, config, state_machine, audio_player):
        self._sm = state_machine       # Remembers which group is currently selected
        self._player = audio_player    # Issues play/stop commands to pygame
        self._sounds = config["sounds"]  # Sound slot data from config.json
        self._active_music = None      # Index of the rune currently playing music, or None
        self._active_ambiance = None   # Index of the rune currently looping ambiance, or None
        gpio = config["gpio"]

        # Create gpiozero Button objects for each pin number listed in config.json.
        # pull_up=True: pin reads HIGH at rest, goes LOW when pressed (standard wiring).
        # bounce_time: ignores signal noise for this many seconds after the first press.
        self._group_buttons = [
            Button(pin, pull_up=True, bounce_time=gpio["button_bounce_time"])
            for pin in gpio["group_buttons"]
        ]
        self._sound_buttons = [
            Button(pin, pull_up=True, bounce_time=gpio["button_bounce_time"])
            for pin in gpio["sound_buttons"]
        ]

        # Assign callbacks. The `i=i` default-argument trick captures the current value of i
        # for each iteration; without it, every lambda would share the last value of i.
        for i, btn in enumerate(self._group_buttons):
            btn.when_pressed = lambda i=i: self._on_group(i)
        for i, btn in enumerate(self._sound_buttons):
            btn.when_pressed = lambda i=i: self._on_sound(i)

    def _on_group(self, index):
        """Called when a group button is pressed. Updates the state machine so subsequent
        rune presses know which category to act on."""
        self._sm.select_group(index)

    def _on_sound(self, index):
        """Called when a rune button (I–VI) is pressed.
        Asks the state machine for the active group, then plays, stops, or switches
        the sound assigned to that rune slot."""
        result = self._sm.select_sound(index)
        if result is None:
            # No group button has been pressed yet — ignore this rune press
            return

        group, sound_index = result
        group_name = group.name.lower()  # e.g. "music", "ambiance", "effects"
        sounds_list = self._sounds.get(group_name, [])
        if sound_index >= len(sounds_list):
            return

        if group_name == "music":
            # Music slots hold a list of file paths (a playlist).
            # Pressing the same rune again stops playback.
            # Pressing a different rune starts that slot's playlist from the beginning.
            paths = sounds_list[sound_index]
            if isinstance(paths, str):
                paths = [paths] if paths else None  # Handle legacy single-string config format
            if self._active_music == sound_index:
                self._player.stop_music()
                self._active_music = None
            elif paths:
                self._player.play_music_playlist(paths)
                self._active_music = sound_index

        elif group_name == "ambiance":
            # Ambiance slots hold a single file path.
            # Pressing the same rune stops the loop; pressing a different rune switches sounds.
            path = sounds_list[sound_index]
            if self._active_ambiance == sound_index:
                self._player.stop_ambiance()
                self._active_ambiance = None
            else:
                self._player.play_ambiance(path)
                self._active_ambiance = sound_index

        elif group_name == "effects":
            # Effects play once and need no toggle tracking.
            path = sounds_list[sound_index]
            self._player.play_effect(path)
