#!/bin/sh
# usage-bridge installer for Linux / macOS
# 1) Copies usage_bridge.py to the install folder
#    (default ~/usage-bridge; choose another by setting USAGE_BRIDGE_HOME)
# 2) Generates a bearer token (token.txt, mode 600, shown once at the end)
# 3) Registers autostart (systemd --user on Linux, launchd on macOS)
# 4) Starts the server and checks /health
# No sudo needed. Re-running is safe: the token is kept, the old process is stopped first.
set -eu

SRC_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DEST="${USAGE_BRIDGE_HOME:-$HOME/usage-bridge}"
echo "Installing usage-bridge to $DEST"
PORT=8787
mkdir -p "$DEST"

command -v python3 >/dev/null 2>&1 || { echo "python3 is required." >&2; exit 1; }
PY=$(command -v python3)

# 1) Server file
cp "$SRC_DIR/usage_bridge.py" "$DEST/usage_bridge.py"

# 2) Token
TOKEN_FILE="$DEST/token.txt"
if [ ! -f "$TOKEN_FILE" ]; then
  TOKEN=$("$PY" -c "import secrets; print(secrets.token_urlsafe(32))")
  (umask 077; printf '%s' "$TOKEN" > "$TOKEN_FILE")
  echo "Generated token: $TOKEN"
  echo "IMPORTANT: send this token to your agent (store it in its secure vault)."
else
  echo "Token already exists at $TOKEN_FILE (unchanged)."
fi
chmod 600 "$TOKEN_FILE"

# Tunnel is Tailscale: bind to this machine's tailnet IPv4 when available,
# so the agent's machine can reach the server through the tailnet only.
# Falls back to 127.0.0.1 when Tailscale is not signed in.
BIND="127.0.0.1"
if command -v tailscale >/dev/null 2>&1; then
  IP4=$(tailscale ip -4 2>/dev/null | head -n 1 || true)
  case "$IP4" in
    100.*) BIND="$IP4" ;;
  esac
fi
if [ "$BIND" = "127.0.0.1" ]; then
  echo "WARNING: Tailscale IPv4 not found. The server will listen on 127.0.0.1 only."
  echo "         Sign in to Tailscale, then re-run this script so it rebinds."
else
  echo "Binding usage-bridge to tailnet address $BIND"
fi

# Stop any older usage-bridge process (it would keep holding the port)
pkill -f "usage_bridge.py" 2>/dev/null || true
sleep 1

OS=$(uname -s)
if [ "$OS" = "Linux" ] && command -v systemctl >/dev/null 2>&1 && systemctl --user show-environment >/dev/null 2>&1; then
  # 3) Autostart via systemd (user)
  UNIT_DIR="$HOME/.config/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/usage-bridge.service" <<EOF
[Unit]
Description=usage-bridge (OpenTokenUsage local API as MCP)
After=network-online.target

[Service]
ExecStart=$PY $DEST/usage_bridge.py --port $PORT --host $BIND
WorkingDirectory=$DEST
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now usage-bridge.service
  echo "Registered systemd user service 'usage-bridge' (starts at login)."
elif [ "$OS" = "Darwin" ]; then
  # 3) Autostart via launchd
  PLIST="$HOME/Library/LaunchAgents/com.usagebridge.server.plist"
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.usagebridge.server</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DEST/usage_bridge.py</string>
    <string>--port</string><string>$PORT</string>
    <string>--host</string><string>$BIND</string>
  </array>
  <key>WorkingDirectory</key><string>$DEST</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict>
</plist>
EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "Registered launchd agent 'com.usagebridge.server' (starts at login)."
else
  # 3) Fallback: start in the background now, no autostart
  (cd "$DEST" && nohup "$PY" "$DEST/usage_bridge.py" --port "$PORT" --host "$BIND" >/dev/null 2>&1 &)
  echo "Started in the background (no autostart available on this system)."
fi

# 4) Health check
sleep 2
if "$PY" - "$BIND" "$PORT" <<'PYEOF'
import json, sys, urllib.request
host, port = sys.argv[1], sys.argv[2]
with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as r:
    print("usage-bridge health:", r.read().decode())
PYEOF
then
  :
else
  echo "WARNING: health check failed (check python3 and that port $PORT is free)." >&2
fi

echo ""
echo "Next steps:"
echo " 1) Make sure the usage provider app (OpenTokenUsage / OpenUsage) is running and signed in."
echo " 2) Make sure Tailscale is signed in on this machine (same account as your agent)."
echo " 3) Hand the token over securely: run  python3 \"$DEST/usage_bridge.py\" --pair  and give your agent the 8-character pairing code (valid 10 minutes, single use) plus this machine's tailnet IPv4 (tailscale ip -4). The agent redeems the code for the token, so the token itself never travels."
