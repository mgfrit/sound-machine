import subprocess
import threading


class BluetoothManager:
    def __init__(self, config_path, on_connected):
        self._config_path = config_path
        self._on_connected = on_connected
        self._busy = False

    def initiate(self, known_devices):
        if self._busy:
            return
        self._busy = True
        threading.Thread(
            target=self._run,
            args=(known_devices,),
            daemon=True
        ).start()

    def _run(self, known_devices):
        try:
            for device in known_devices:
                result = self._connect(device["address"])
                if result == "connected":
                    self._route_audio(device["address"])
                    self._on_connected()
                    return
                elif result == "already_connected":
                    return
        finally:
            self._busy = False

    def _route_audio(self, address):
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
        proc = subprocess.run(
            ["bluetoothctl", "connect", address],
            capture_output=True, text=True, timeout=15
        )
        if "Connection successful" in proc.stdout:
            return "connected"
        if "Already connected" in proc.stdout or "Connected: yes" in proc.stdout:
            return "already_connected"
        return None
