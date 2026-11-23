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

To report a vulnerability, please open a private report via the repository's
security advisories, or contact the maintainer directly instead of filing a
public issue.
