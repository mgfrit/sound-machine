import json
import os
import signal
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
    state_machine = StateMachine()

    bt_sound_path = config["system_sounds"].get("bt_connected")

    def on_bt_connected():
        if bt_sound_path and Path(bt_sound_path).exists():
            player.play_system_sound(bt_sound_path)

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

    ButtonHandler(
        config=config,
        state_machine=state_machine,
        audio_player=player,
        on_bt_held=on_bt_held,
    )

    print("D&D Sound Machine running. Press Ctrl+C to exit.")
    signal.pause()

if __name__ == "__main__":
    main()
