#!/bin/sh
# usage-bridge uninstaller for Linux / macOS
# Stops the server, removes the autostart registration and the install folder.
# Default ~/usage-bridge; if you installed elsewhere, set USAGE_BRIDGE_HOME
# to the same folder you used at install time.
set -eu

DEST="${USAGE_BRIDGE_HOME:-$HOME/usage-bridge}"
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
# The token may also live in OS secure storage, outside $DEST — remove it too.
if [ "$OS" = "Darwin" ]; then
  security delete-generic-password -s usage-bridge -a token >/dev/null 2>&1 || true
fi
if command -v secret-tool >/dev/null 2>&1; then
  secret-tool clear service usage-bridge account token >/dev/null 2>&1 || true
fi
rm -rf "$DEST"
echo "Removed $DEST and the stored token (secure storage / token.txt)."
echo "Done. If the provider app (OpenTokenUsage / OpenUsage) is no longer needed,"
echo "uninstall it separately; this script does not touch it."
