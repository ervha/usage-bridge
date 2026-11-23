# Security notes

usage-bridge exposes your AI subscription *usage amounts* (not credentials,
not prompts, not code) to machines you allow onto your private network.
Treat it like any other internal service:

- Reach it only over a private tailnet / tunnel. Never publish port 8787
  directly on the internet, and never enable a public funnel for it.
- Always configure a bearer token. The installers create it in OS
  secure storage via `usage_bridge.py --init-token` (Windows DPAPI,
  macOS Keychain, Linux Secret Service; `token.txt` with owner-only
  permissions is the fallback where no secure store exists, and
  `USAGE_BRIDGE_TOKEN` can override). If no token is configured,
  authentication is disabled — in that mode keep the bind address on
  `127.0.0.1` only. The server prints a warning at startup when no
  token is set, and prints where the token came from (`token source:`).
- Keep token files out of version control (they are listed in
  `.gitignore`). Rotate the token by removing the stored one
  (uninstall, or delete `token.dpapi` / the Keychain entry / `token.txt`)
  and re-running `--init-token`, then pair again.
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
- **The token is protected by your OS user account, not by magic.** By
  default it is kept in OS secure storage (DPAPI-encrypted on Windows,
  Keychain on macOS, Secret Service on Linux), so it survives restarts
  without sitting in backups or synced folders as plain text. But
  anything running as your user can ask the OS for it — malware already
  running as your user could retrieve it, though at that point it could
  also read OpenTokenUsage directly. The plain-text fallback
  (`token.txt`, mode 600) is weaker; keep it out of synced folders.
  Rotate the token if you suspect a local compromise. (An ephemeral
  mode, `USAGE_BRIDGE_EPHEMERAL=1`, stores nothing at all and rotates
  the token on every restart, at the cost of re-pairing each time.)
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
  removes the server, the autostart entry, and the stored token.

## Where things live

- The “server” is the `usage_bridge.py` process on your own PC — there is
  no hosted service and no third party in the path.
- The token exists in exactly two places: the PC's OS secure storage
  (a DPAPI-encrypted file on Windows, a Keychain entry on macOS, a
  Secret Service entry on Linux; a plain `token.txt` only as fallback)
  and your agent's secret store.
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
