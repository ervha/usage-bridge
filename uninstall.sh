#!/bin/sh
# usage-bridge uninstaller for Linux / macOS
# Stops the server, removes the autostart registration and ~/usage-bridge.
set -eu

DEST="$HOME/usage-bridge"
OS=$(uname -s)

if [ "$OS" = "Linux" ] && command -v systemctl >/dev/null 2>&1; then
  systemctl --user disable --now usage-bridge.service 2>/dev/null || true
  rm -f "$HOME/.config/systemd/user/usage-bridge.service"
  systemctl --user daemon-reload 2>/dev/null || true
  echo "Removed systemd user service."
fi
if [ "$OS" = "Darwin" ]; then
  PLIST="$HOME/Library/LaunchAgents/com.usagebridge.server.plist"
  launchctl unload "$PLIST" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Removed launchd agent."
fi

pkill -f "usage_bridge.py" 2>/dev/null || true
rm -rf "$DEST"
echo "Removed $DEST (including token.txt)."
echo "Done. If the provider app (OpenTokenUsage / OpenUsage) is no longer needed,"
echo "uninstall it separately; this script does not touch it."
