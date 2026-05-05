import json
import signal
from pathlib import Path
import pygame

from state_machine import StateMachine
from audio_player import AudioPlayer
from button_handler import ButtonHandler

def load_config(path="config.json"):
    with open(path) as f:
        return json.load(f)

def main():
    config = load_config()
    pygame.init()

    player = AudioPlayer(volumes=config["audio"])
    state_machine = StateMachine()

    def on_bt_held():
        print("Bluetooth button held — BT logic will be added in Phase 2")

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
