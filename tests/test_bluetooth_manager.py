from unittest.mock import patch, MagicMock, call
import bluetooth_manager


def test_run_connects_to_first_known_device():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    with patch.object(bt, '_connect', return_value="connected") as mock_connect, \
         patch.object(bt, '_route_audio'):
        bt._run([{"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker"}])
    mock_connect.assert_called_once_with("AA:BB:CC:DD:EE:FF")
    assert called == [True]


def test_run_tries_next_if_first_fails():
    called = []
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: called.append(True)
    )
    with patch.object(bt, '_connect', side_effect=[None, "connected"]) as mock_connect, \
         patch.object(bt, '_route_audio'):
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
    with patch.object(bt, '_connect', return_value="connected") as mock_connect, \
         patch.object(bt, '_route_audio'):
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


def test_run_routes_audio_after_connect():
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: None
    )
    with patch.object(bt, '_connect', return_value="connected"), \
         patch.object(bt, '_route_audio') as mock_route:
        bt._run([{"address": "AA:BB:CC:DD:EE:FF", "name": "Speaker"}])
    mock_route.assert_called_once_with("AA:BB:CC:DD:EE:FF")


def test_route_audio_sets_sink_and_moves_inputs():
    bt = bluetooth_manager.BluetoothManager(
        config_path="config.json",
        on_connected=lambda: None
    )
    list_result = MagicMock(stdout="42\t-\t-\t-\t-\n", returncode=0)
    ok = MagicMock(returncode=0)
    with patch("bluetooth_manager.subprocess.run", side_effect=[ok, ok, list_result, ok]) as mock_run:
        bt._route_audio("AA:BB:CC:DD:EE:FF")
    commands = [c.args[0] for c in mock_run.call_args_list]
    sink = "bluez_sink.AA_BB_CC_DD_EE_FF.a2dp_sink"
    assert any("set-default-sink" in cmd and sink in cmd for cmd in commands)
    assert any("move-sink-input" in cmd and "42" in cmd and sink in cmd for cmd in commands)
