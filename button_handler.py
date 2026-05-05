from gpiozero import Button

class ButtonHandler:
    def __init__(self, config, state_machine, audio_player, on_bt_held):
        self._sm = state_machine
        self._player = audio_player
        self._sounds = config["sounds"]
        gpio = config["gpio"]

        self._group_buttons = [
            Button(pin, pull_up=True, bounce_time=gpio["button_bounce_time"])
            for pin in gpio["group_buttons"]
        ]
        self._sound_buttons = [
            Button(pin, pull_up=True, bounce_time=gpio["button_bounce_time"])
            for pin in gpio["sound_buttons"]
        ]
        self._bt_button = Button(
            gpio["bluetooth_button"],
            pull_up=True,
            hold_time=gpio["bluetooth_hold_time"]
        )

        for i, btn in enumerate(self._group_buttons):
            btn.when_pressed = lambda i=i: self._on_group(i)
        for i, btn in enumerate(self._sound_buttons):
            btn.when_pressed = lambda i=i: self._on_sound(i)

        self._bt_button.when_held = on_bt_held

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
        path = sounds_list[sound_index]
        if group_name == "music":
            self._player.play_music(path)
        elif group_name == "ambiance":
            self._player.play_ambiance(path)
        elif group_name == "effects":
            self._player.play_effect(path)
