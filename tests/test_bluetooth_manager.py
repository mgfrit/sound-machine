from unittest.mock import patch
import bluetooth_manager


def test_run_connects_to_first_known_device():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    with patch.object(bt, '_connect', return_value="connected") as mock_connect:
        bt._run([{"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker"}])
    mock_connect.assert_called_once_with("AA:BB:CC:DD:EE:FF")
    assert called == [True]


def test_run_tries_next_if_first_fails():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    with patch.object(bt, '_connect', side_effect=[None, "connected"]) as mock_connect:
        bt._run([
            {"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker1"},
            {"address": "11:22:33:44:55:66", "name": "Speaker2"},
        ])
    assert mock_connect.call_count == 2
    assert called == [True]


def test_run_stops_after_first_success():
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: None
    )
    with patch.object(bt, '_connect', return_value="connected") as mock_connect:
        bt._run([
            {"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker1"},
            {"address": "11:22:33:44:55:66", "name": "Speaker2"},
        ])
    mock_connect.assert_called_once_with("AA:BB:CC:DD:EE:FF")


def test_run_no_callback_when_none_connect():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    with patch.object(bt, '_connect', return_value=None):
        bt._run([{"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker"}])
    assert called == []


def test_run_already_connected_no_callback():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    with patch.object(bt, '_connect', return_value="already_connected"):
        bt._run([{"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker"}])
    assert called == []


def test_run_empty_list_no_error():
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: None
    )
    bt._run([])
