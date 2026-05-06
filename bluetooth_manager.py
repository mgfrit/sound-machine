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
                    self._on_connected()
                    return
                elif result == "already_connected":
                    return
        finally:
            self._busy = False

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
