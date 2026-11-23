# Security notes

usage-bridge exposes your AI subscription *usage amounts* (not credentials,
not prompts, not code) to machines you allow onto your private network.
Treat it like any other internal service:

- Reach it only over a private tailnet / tunnel. Never publish port 8787
  directly on the internet, and never enable a public funnel for it.
- Always configure a bearer token (`USAGE_BRIDGE_TOKEN` or `token.txt`).
  If no token is configured, authentication is disabled — in that mode keep
  the bind address on `127.0.0.1` only. The server prints a warning at
  startup when no token is set.
- Keep `token.txt` out of version control (it is listed in `.gitignore`).
  Rotate it by replacing the file and restarting the server.
- The server is read-only and depends only on the Python standard library,
  which keeps the supply-chain surface small.
- OpenTokenUsage itself holds the provider sign-ins on your PC. This bridge
  never reads, stores, or forwards those credentials; it only relays the
  aggregated usage JSON from the local API.

## Risks you accept by using this

- **Your usage patterns become queryable on your tailnet.** The data is
  amounts and reset times — not credentials, prompts, or code — but it
  does reveal which subscriptions you pay for, your plan tiers, and
  roughly when you are active. Anyone who obtains the token can read it
  until you rotate the token.
- **Every device on your tailnet can reach the server.** A compromised
  device still needs the token to read usage data, but the
  unauthenticated `/health` endpoint tells it that the service exists
  and the PC is awake. Only put devices you trust on the tailnet.
- **Pairing has a 10-minute window.** During it, someone who learns the
  code *and* is on your tailnet could redeem it first and receive the
  token. Codes are single-use, burn after 5 wrong guesses, and can only
  be created on the PC itself — but do not post a live code publicly.
- **The token sits on disk** (`token.txt`; mode 600 on Linux / macOS,
  user-profile ACLs on Windows). Malware already running as your user
  could read it — though at that point it could also read OpenTokenUsage
  directly. Rotate the token if you suspect a local compromise.
- **Readings are only as good as an undocumented API.** OpenTokenUsage's
  local API is not a public contract; an app update could change its
  shape and produce wrong (not just stale) readings, and an agent
  routing models on wrong numbers will make wrong choices.
  Sanity-check surprising readings against the tray app.
- **What the agent reads enters the agent's world.** Quota snapshots may
  end up in your agent's conversation history or logs, wherever those
  are stored.
- **It runs at every logon until uninstalled.** The autostart entry
  keeps the server reachable whenever the PC is on. Uninstalling
  removes the server, the autostart entry, and the token file.

## Where things live

- The “server” is the `usage_bridge.py` process on your own PC — there is
  no hosted service and no third party in the path.
- The token exists in exactly two places: `token.txt` on the PC and your
  agent's secret store.
- Pairing codes are never stored as-is. The server keeps only a SHA-256
  hash, an expiry (10 minutes) and a failure counter, all in process
  memory; restarting the server erases them. A redeemed or expired code
  cannot be used again.
- The bridge never reads, stores, or forwards your provider credentials
  (those stay inside OpenTokenUsage) and sends nothing anywhere except
  back to the agent that asked, inside your tailnet.

To report a vulnerability, please open a private report via the repository's
security advisories, or contact the maintainer directly instead of filing a
public issue.
