import json
import re
import subprocess
import threading


class BluetoothManager:
    def __init__(self, config_path, on_connected):
        self._config_path = config_path
        self._on_connected = on_connected
        self._busy = False

    def initiate(self, saved_address, scan_timeout):
        if self._busy:
            return
        self._busy = True
        threading.Thread(
            target=self._run,
            args=(saved_address, scan_timeout),
            daemon=True
        ).start()

    def _run(self, saved_address, scan_timeout):
        try:
            if saved_address:
                result = self._connect(saved_address)
                if result == "connected":
                    self._trigger_connected(saved_address)
                    return
                elif result == "already_connected":
                    return  # already connected, no sound
            devices = self._scan(scan_timeout)
            for device in devices:
                result = self._connect(device["address"])
                if result == "connected":
                    self._trigger_connected(device["address"])
                    return
        finally:
            self._busy = False

    def _scan(self, timeout):
        result = subprocess.run(
            ["bluetoothctl", "--timeout", str(timeout), "scan", "on"],
            capture_output=True, text=True
        )
        return self._parse_scan_output(result.stdout)

    def _parse_scan_output(self, output):
        devices = []
        for line in output.splitlines():
            match = re.search(r'\[NEW\] Device ([0-9A-F:]{17}) (.+)', line)
            if match:
                devices.append({"address": match.group(1), "name": match.group(2)})
        return devices

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

    def _trigger_connected(self, address):
        self._save_device(address)
        self._on_connected()

    def _save_device(self, address):
        try:
            with open(self._config_path) as f:
                config = json.load(f)
            config["bluetooth"]["saved_device_address"] = address
            with open(self._config_path, "w") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass
