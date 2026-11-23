# Changelog

## [1.0.0] - 2026-11-23

First public release.

- MCP server (`usage_all` / `usage_provider`) relaying OpenTokenUsage's
  local API to agents on other machines, over Tailscale only
- Bearer-token auth, 5-minute cache, stale fallback on upstream errors
- Pairing: one-time 8-character codes for secure token handover — the
  long-lived token never travels through chat
- Token kept in OS secure storage (Windows DPAPI, macOS Keychain,
  Linux Secret Service), with a `token.txt` fallback and an optional
  memory-only ephemeral mode
- Installers for Windows (PowerShell) and Linux / macOS (sh):
  selectable install folder, logon autostart, health check;
  uninstallers included
- Companion agent skill ([skill/SKILL.md](skill/SKILL.md)): when to
  check quotas, how to present them, and how to turn them into model
  choices
