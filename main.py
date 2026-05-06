import json
import os
import signal
import sys
from pathlib import Path

os.environ.setdefault("SDL_AUDIODRIVER", "pulse")

from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory
Device.pin_factory = LGPIOFactory()

import pygame
from state_machine import StateMachine
from audio_player import AudioPlayer
from button_handler import ButtonHandler
from bluetooth_manager import BluetoothManager


def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)


def main():
    config = load_config()
    pygame.init()

    player = AudioPlayer(volumes=config["audio"])

    # Music streams via pygame.mixer.music — only preload ambiance, effects, system sounds
    preload_paths = (
        [p for p in config["sounds"].get("ambiance", []) if p] +
        [p for p in config["sounds"].get("effects", []) if p]
    )
    bt_sound = config["system_sounds"].get("bt_connected")
    if bt_sound:
        preload_paths.append(bt_sound)
    player.preload(preload_paths)

    # Play BT connected sound on boot if a device is already configured
    if bt_sound and Path(bt_sound).exists() and config["bluetooth"].get("saved_device_address"):
        player.play_system_sound(bt_sound)

    state_machine = StateMachine()

    def on_bt_connected():
        if bt_sound and Path(bt_sound).exists():
            player.play_system_sound(bt_sound)

    bt_manager = BluetoothManager(
        config_path="config.json",
        on_connected=on_bt_connected,
    )

    def on_bt_held():
        bt_cfg = config["bluetooth"]
        bt_manager.initiate(
            saved_address=bt_cfg.get("saved_device_address"),
            scan_timeout=bt_cfg.get("scan_timeout", 10),
        )

    handler = ButtonHandler(
        config=config,
        state_machine=state_machine,
        audio_player=player,
        on_bt_held=on_bt_held,
    )

    def shutdown(signum, frame):
        for btn in handler._group_buttons + handler._sound_buttons:
            btn.close()
        handler._bt_button.close()
        Device.pin_factory.close()
        pygame.quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print("D&D Sound Machine running. Press Ctrl+C to exit.")
    signal.pause()


if __name__ == "__main__":
    main()
