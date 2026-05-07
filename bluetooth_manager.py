import subprocess
import threading


# Handles automatic Bluetooth speaker connection at device startup.
# Tries each saved ("known") device in order until one connects successfully.
# Runs in a background thread so it doesn't block the main audio event loop
# while bluetoothctl negotiates the connection (which can take several seconds).
class BluetoothManager:
    def __init__(self, config_path, on_connected):
        self._config_path = config_path   # Path to config.json (reserved for future use)
        self._on_connected = on_connected  # Callback invoked after a successful connection — plays the chime
        self._busy = False                 # Prevents starting a second connection thread if one is already running

    def initiate(self, known_devices):
        """Kick off the auto-connect process in a background thread.
        known_devices is the list of saved speakers from config.json,
        each a dict with 'address' (MAC) and 'name' keys."""
        if self._busy:
            return
        self._busy = True
        threading.Thread(
            target=self._run,
            args=(known_devices,),
            daemon=True  # Thread is killed automatically when the main process exits
        ).start()

    def _run(self, known_devices):
        """Background thread body: iterate known devices and stop as soon as one connects."""
        try:
            for device in known_devices:
                result = self._connect(device["address"])
                if result == "connected":
                    # Switch PulseAudio's output to this speaker, then play the connection chime
                    self._route_audio(device["address"])
                    self._on_connected()
                    return
                elif result == "already_connected":
                    # Device was already connected from a previous session — nothing to do
                    return
        finally:
            self._busy = False

    def _route_audio(self, address):
        """Point PulseAudio at the Bluetooth speaker so all subsequent audio goes through it.

        PulseAudio names Bluetooth sinks using underscores instead of colons in the MAC address,
        e.g. F4:4E:FD:1B:D4:97 becomes bluez_sink.F4_4E_FD_1B_D4_97.a2dp_sink.

        Steps:
          1. Activate the A2DP profile (high-quality stereo) on the Bluetooth audio card.
          2. Set that sink as the system-wide default output.
          3. Move any streams already playing to the new sink (handles audio that started before BT connected)."""
        sanitized = address.replace(":", "_")
        pactl = ["pactl", "--server", "unix:/run/user/1000/pulse/native"]
        sink = f"bluez_sink.{sanitized}.a2dp_sink"
        subprocess.run(pactl + ["set-card-profile", f"bluez_card.{sanitized}", "a2dp_sink"],
                       capture_output=True, text=True)
        subprocess.run(pactl + ["set-default-sink", sink], capture_output=True, text=True)
        result = subprocess.run(pactl + ["list", "sink-inputs", "short"],
                                capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts:
                subprocess.run(pactl + ["move-sink-input", parts[0], sink],
                               capture_output=True, text=True)

    def _connect(self, address):
        """Attempt to connect to a Bluetooth device by MAC address using bluetoothctl.
        Returns 'connected', 'already_connected', or None if the attempt failed."""
        proc = subprocess.run(
            ["bluetoothctl", "connect", address],
            capture_output=True, text=True, timeout=15
        )
        if "Connection successful" in proc.stdout:
            return "connected"
        if "Already connected" in proc.stdout or "Connected: yes" in proc.stdout:
            return "already_connected"
        return None
