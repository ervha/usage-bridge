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
