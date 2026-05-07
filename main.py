import json
import os
import signal
import sys
import time
from pathlib import Path

# Tell SDL (pygame's audio backend) to use PulseAudio instead of ALSA.
# Must be set before pygame is imported — once the mixer initialises it reads
# the environment and won't re-read it later.
# PulseAudio is what routes audio to the Bluetooth speaker on this Pi.
os.environ.setdefault("SDL_AUDIODRIVER", "pulse")

from gpiozero import Device
from gpiozero.pins.lgpio import LGPIOFactory

# gpiozero supports several GPIO backends. LGPIOFactory is the modern one that
# works with the newer kernel GPIO character-device interface (lgpio library).
# It must be set before any Button objects are created.
Device.pin_factory = LGPIOFactory()

import pygame
from state_machine import StateMachine
from audio_player import AudioPlayer, MUSIC_END
from button_handler import ButtonHandler
from bluetooth_manager import BluetoothManager


def load_config(path="config.json"):
    """Read and return the entire config.json as a Python dict."""
    with open(path) as f:
        return json.load(f)


def main():
    config = load_config()

    # pygame.init() initialises all pygame modules. The audio mixer is one of
    # them, but AudioPlayer calls pygame.mixer.init() itself with specific
    # settings (sample rate, buffer size), which overrides the defaults.
    pygame.init()

    player = AudioPlayer(volumes=config["audio"])

    # Preload short sounds into pygame's in-memory cache so they play instantly.
    # Music is excluded because music files are too large to hold in RAM —
    # they're streamed from disk via pygame.mixer.music instead.
    preload_paths = (
        [p for p in config["sounds"].get("ambiance", []) if p] +
        [p for p in config["sounds"].get("effects", []) if p]
    )
    bt_sound = config["system_sounds"].get("bt_connected")
    if bt_sound:
        preload_paths.append(bt_sound)
    player.preload(preload_paths)

    state_machine = StateMachine()

    # Callback invoked by BluetoothManager after a speaker connects.
    # Plays the connection chime so the user knows the speaker is ready.
    # The path-existence check guards against a missing or misconfigured file.
    def on_bt_connected():
        if bt_sound and Path(bt_sound).exists():
            player.play_system_sound(bt_sound)

    # Start the background Bluetooth auto-connect thread.
    # It iterates known_devices in order and stops at the first successful connection.
    bt_manager = BluetoothManager(
        config_path="config.json",
        on_connected=on_bt_connected,
    )
    bt_manager.initiate(config["bluetooth"].get("known_devices", []))

    # Wire the physical GPIO buttons to the state machine and audio player.
    # ButtonHandler registers gpiozero callbacks — no polling needed.
    handler = ButtonHandler(
        config=config,
        state_machine=state_machine,
        audio_player=player,
    )

    def shutdown(signum, frame):
        """Clean-up handler for SIGTERM (systemd stop) and SIGINT (Ctrl+C).
        Releases GPIO pins and the pygame mixer before exiting."""
        for btn in handler._group_buttons + handler._sound_buttons:
            btn.close()
        Device.pin_factory.close()
        pygame.quit()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    print("D&D Sound Machine running. Press Ctrl+C to exit.")

    # Main event loop — runs forever until a signal arrives.
    # pygame needs its event queue drained regularly or it can stall.
    # The only event we act on is MUSIC_END, which fires when a music track
    # finishes playing naturally. advance_playlist() then loads and plays
    # the next track in the current playlist with a crossfade.
    # sleep(0.05) keeps CPU usage near-zero between events (20 checks/second).
    while True:
        for event in pygame.event.get():
            if event.type == MUSIC_END:
                player.advance_playlist()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
