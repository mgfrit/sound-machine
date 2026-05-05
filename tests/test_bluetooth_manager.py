import pytest
from unittest.mock import MagicMock, patch
import bluetooth_manager

def test_trigger_connected_calls_callback():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    bt._trigger_connected("AA:BB:CC:DD:EE:FF")
    assert called == [True]

def test_parse_scan_output_extracts_devices():
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: None
    )
    raw = (
        "[NEW] Device AA:BB:CC:DD:EE:FF MySpeaker\n"
        "[NEW] Device 11:22:33:44:55:66 AnotherDevice\n"
        "Discovery started\n"
    )
    devices = bt._parse_scan_output(raw)
    assert devices == [
        {"address": "AA:BB:CC:DD:EE:FF", "name": "MySpeaker"},
        {"address": "11:22:33:44:55:66", "name": "AnotherDevice"},
    ]

def test_parse_scan_output_empty_string():
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: None
    )
    assert bt._parse_scan_output("") == []
