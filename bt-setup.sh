#!/bin/bash
PULSE_SOCKET="unix:/run/user/1000/pulse/native"

# Wait for PulseAudio socket to be ready
for i in $(seq 1 30); do
    pactl --server "$PULSE_SOCKET" info >/dev/null 2>&1 && break
    sleep 1
done

# Connect to Bluetooth speaker
bluetoothctl connect F4:4E:FD:1B:D4:97 || true

# Wait for device to appear in PulseAudio
for i in $(seq 1 20); do
    pactl --server "$PULSE_SOCKET" list cards 2>/dev/null | grep -q "bluez_card" && break
    sleep 1
done

sleep 3

# Switch to A2DP — allow failure so service still starts
pactl --server "$PULSE_SOCKET" set-card-profile bluez_card.F4_4E_FD_1B_D4_97 a2dp_sink || true
pactl --server "$PULSE_SOCKET" set-default-sink bluez_sink.F4_4E_FD_1B_D4_97.a2dp_sink || true

exit 0
