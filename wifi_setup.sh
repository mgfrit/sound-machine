#!/bin/bash
# Waits up to 30s for wlan0 to get an IP. If none, activates a WiFi hotspot
# so the user can configure a new network via the web UI at 192.168.4.1:5000/wifi.

SSID="SoundMachine-Setup"
PASSWORD="soundmachine1"

for i in $(seq 1 30); do
    if ip addr show wlan0 2>/dev/null | grep -q "inet "; then
        echo "wlan0 connected — skipping hotspot setup."
        exit 0
    fi
    sleep 1
done

echo "No WiFi connection after 30s — activating hotspot '$SSID'."
nmcli device wifi hotspot ifname wlan0 ssid "$SSID" password "$PASSWORD"
echo "Hotspot active. Connect to '$SSID' and open http://soundmachine.local:5000/wifi"
echo "(Fallback IP: http://10.42.0.1:5000/wifi)"
exit 0
