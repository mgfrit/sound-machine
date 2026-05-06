#!/bin/bash
# One-time setup: enables clean URLs (soundmachine.local instead of IP:5000).
# Safe to run multiple times. Does not touch Flask or existing services.

set -e

HOSTNAME="soundmachine"
NGINX_CONF="/etc/nginx/sites-available/soundmachine"
NGINX_ENABLED="/etc/nginx/sites-enabled/soundmachine"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Sound Machine URL setup ==="

# 1. Set hostname
current=$(hostname)
if [ "$current" != "$HOSTNAME" ]; then
    echo "Setting hostname: $current -> $HOSTNAME"
    sudo hostnamectl set-hostname "$HOSTNAME"
else
    echo "Hostname already set to '$HOSTNAME' — skipping."
fi

# 2. Install avahi-daemon and nginx if missing
PACKAGES=""
dpkg -s avahi-daemon &>/dev/null || PACKAGES="$PACKAGES avahi-daemon"
dpkg -s nginx        &>/dev/null || PACKAGES="$PACKAGES nginx"

if [ -n "$PACKAGES" ]; then
    echo "Installing:$PACKAGES"
    sudo apt-get install -y $PACKAGES
else
    echo "avahi-daemon and nginx already installed — skipping."
fi

# 3. Enable and start avahi
sudo systemctl enable avahi-daemon
sudo systemctl start  avahi-daemon

# 4. Install nginx site config
sudo cp "$SCRIPT_DIR/soundmachine-nginx.conf" "$NGINX_CONF"

# Remove default site if present (it conflicts on port 80)
[ -L /etc/nginx/sites-enabled/default ] && sudo rm /etc/nginx/sites-enabled/default

# Enable soundmachine site
[ -L "$NGINX_ENABLED" ] || sudo ln -s "$NGINX_CONF" "$NGINX_ENABLED"

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl reload nginx

echo ""
echo "Done. Access the web UI at:"
echo "  http://soundmachine.local        (main interface)"
echo "  http://soundmachine.local/wifi   (WiFi setup, when in hotspot mode)"
echo ""
echo "The old IP:5000 address still works as a fallback."
