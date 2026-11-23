# usage-bridge

**Let your AI agent see its own remaining quota — before it picks a model.**

AI coding agents (Claude Code, Codex, Antigravity, Grok, …) each have their own
session / weekly limits and reset times, but orchestrators such as T3 Code
cannot read those remaining quotas through their MCP surface. So a human has
to check every dashboard, remember every reset, and choose a model by hand.

`usage-bridge` fixes that. It relays the local API of
[OpenTokenUsage](https://www.poweruserz.dev/) — a Windows tray app that already
collects all those limits in one place — as a small MCP server, reachable
privately over [Tailscale](https://tailscale.com/). Any MCP-capable agent can
then read the remaining quota and decide for itself which model to use next.

> 人間が枠を管理する時代から、AIが自分の枠を見て動く時代へ。

## How it works

```text
OpenTokenUsage (Windows tray, local API 127.0.0.1:6736/v1/usage)
        │
        ▼
usage_bridge.py  — stdlib-only Python, no pip installs
  • MCP Streamable HTTP: POST /mcp
  • Tools: usage_all / usage_provider
  • Bearer-token auth, 5-minute cache, stale fallback on upstream errors
        │
        ▼  Tailscale (tailnet only — no port forwarding, nothing public)
        │
        ▼
Your AI agent / orchestrator (e.g. T3 Code)
  reads remaining quota → picks the model → starts the thread
```

Example decisions an agent can make with this data:

- “Argon has plenty left → use it for the first-pass review”
- “Neon is close to its weekly cap → route implementation to Sonnet”
- “Opus is scarce this week → save it for the hard problem”

## Requirements

- Windows PC with Python 3.10+
- [OpenTokenUsage](https://www.poweruserz.dev/) installed and signed in
  (`winget install PowerUserZ.OpenTokenUsage`)
- [Tailscale](https://tailscale.com/) signed in on the PC **and** on the
  machine where your agent runs (same tailnet)

## Install (Windows)

### 0. Before you start

- Sign in to **Tailscale** on this PC first, and note its tailnet IPv4
  (`tailscale ip -4`, a `100.x…` address). If you run the installer before
  signing in, it falls back to `127.0.0.1` — just sign in and run it again.
- Make sure `python --version` (or `py --version`) works in PowerShell.

### 1. Get the files

Download `usage-bridge-v1.0.0.zip` from the
[latest release](https://github.com/ervha/usage-bridge/releases/latest)
and unzip it (or clone this repository). Open PowerShell in that folder.

### 2. Run the installer

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

The installer:

1. Installs OpenTokenUsage and Tailscale via `winget` if missing
2. Copies `usage_bridge.py` to `%USERPROFILE%\usage-bridge`
3. Generates a bearer token (`token.txt`, shown once — store it in a
   password manager / secure vault, never commit it, never share it
   publicly)
4. Binds the server to your PC's tailnet IPv4 (`100.x…`) — falling back to
   `127.0.0.1` with a warning if Tailscale is not signed in yet
5. Registers logon autostart in your Startup folder (no admin rights
   needed; the server launches windowless via `pythonw`) and health-checks
   `GET /health`. Re-running the installer first stops any older
   usage-bridge process, so a stale copy cannot keep holding port 8787.

### 3. Enable your providers

Open OpenTokenUsage once, enable the providers you use (Claude / Codex /
Antigravity / Grok / …) and confirm each one is signed in. The bridge can
only relay what OpenTokenUsage can see.

### 4. Verify

```powershell
# Health (no auth needed) — use your own tailnet IPv4:
Invoke-RestMethod http://<tailnet IPv4>:8787/health
# → {"ok": true, "service": "usage-bridge"}

# Usage (auth required):
$token = Get-Content ~\usage-bridge\token.txt
Invoke-RestMethod http://<tailnet IPv4>:8787/usage -Headers @{ Authorization = "Bearer $token" }
```

From the agent's machine, repeat the health check to confirm the tailnet
path works end to end. A `401` on `/usage` means the token does not match;
a timeout means the PC is asleep, the server is not running, or the two
machines are not on the same tailnet.

### Manual run (instead of the installer)

```powershell
python usage_bridge.py --host 127.0.0.1 --port 8787
```

## Updating

Download the new release zip, unzip it, and run `install.ps1` again.
Your existing `token.txt` is kept, the old server process is stopped
first, and autostart is re-registered against your current tailnet IPv4.
No other state is stored, so there is nothing to migrate.

## Connecting an MCP client

Point any MCP client at:

```text
POST http://<your PC's tailnet IPv4>:8787/mcp
Authorization: Bearer <your token>
```

Tools:

| Tool | Description |
|---|---|
| `usage_all` | Snapshots for all enabled providers (`displayName` / `plan` / usage lines, plus `fetchedAt` and a `stale` flag) |
| `usage_provider` | One provider by id, e.g. `claude`, `codex`, `antigravity`, `grok` |

Plain-JSON debugging endpoints: `GET /health`, `GET /usage` (auth required).

## Security — read this first

- **Never port-forward port 8787 to the internet.** Reach it only inside
  your tailnet (or another private tunnel you control).
- Always set a token (`USAGE_BRIDGE_TOKEN` env var or `token.txt`). Without
  one, auth is disabled and the server must stay on `127.0.0.1` only.
- The bridge is **read-only**. It has no write tools.
- Usage data stays between your PC and your agent. Nothing is sent to any
  third-party service by this code.
- See [SECURITY.md](SECURITY.md) for the full notes.

## Limitations

- The PC must be awake. If it sleeps, the agent cannot reach the bridge
  (same constraint as any locally hosted orchestrator).
- OpenTokenUsage's local API is not a public, versioned API — an app update
  could change its shape. The 5-minute cache and stale fallback soften
  transient failures, but a format change may need a bridge update.
- Windows-first: the installer is PowerShell. The server itself is plain
  Python and can be run by hand on other platforms if you have an equivalent
  usage source.

## Uninstall

1. Stop the running server:

   ```powershell
   Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
     Where-Object { $_.CommandLine -like "*usage_bridge.py*" } |
     ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   ```

2. Remove the autostart entry: delete `usage-bridge.cmd` from your
   Startup folder (`shell:startup` in Explorer's address bar opens it).
3. Delete the install folder: `%USERPROFILE%\usage-bridge`
   (this also deletes `token.txt` — the token is then useless to anyone,
   because the server is gone).
4. Remove the MCP entry / endpoint from your agent's configuration, so
   the agent stops trying to reach the bridge.
5. Optional, only if you installed them for this: uninstall
   OpenTokenUsage and Tailscale via `winget uninstall` or Windows
   Settings. Nothing else was installed and no registry settings are
   left behind by usage-bridge itself.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Health check fails right after install | Python not on PATH, or port 8787 already in use. Re-run the installer (it stops older usage-bridge processes first). |
| Installer warns “Tailscale IPv4 not found” | Tailscale is not signed in yet. Sign in, then re-run the installer so it rebinds to the tailnet address. |
| `401 unauthorized` from the agent | Token mismatch. Use the exact contents of `%USERPROFILE%\usage-bridge\token.txt` as the Bearer token. |
| Agent gets an empty reply | Fixed in v1.0.0: windowless (`pythonw`) startup no longer breaks responses. Make sure you are not running an older copy — re-run the installer. |
| `OpenTokenUsage local API unreachable` | OpenTokenUsage is not running, or no provider is enabled. Open it once and check its tray icon. |
| Nothing answers at all | The PC is asleep/off, or the agent is on a different tailnet. Wake the PC and check `tailscale status` on both machines. |

## Related projects — and how this differs

Quota / usage MCP servers do exist. What we could not find is another one
built on OpenTokenUsage, or one designed for an agent running on a
*different machine* than the PC that holds the sign-ins.

- [agent-runway](https://github.com/jberdah/agent-runway) — the closest in
  spirit: remaining quota and resets for Claude / Codex / Copilot / Gemini
  CLI via CLI, skill and MCP, to judge whether work can start now. It reads
  each provider's endpoints itself and is aimed at the same machine.
- [tokenhud](https://github.com/ZhuoQiuMcgill/tokenhud) — terminal HUD plus
  MCP server for Claude / Codex limits and cost history. Focused on
  visibility and history, not on model routing.
- [ai-usage-mcp](https://github.com/MohitBansal321/ai-usage-mcp) — local MCP
  server + CLI for token / cost analysis and Pro / Max plan limits
  (Claude / Codex / OpenCode).
- [tokenmeter-tray](https://github.com/DDRG15/tokenmeter-tray) — tray
  tracker with a read-only MCP server, mainly Claude / Codex.

usage-bridge differs in three ways:

1. **Source** — it relays OpenTokenUsage's already-aggregated quotas
   (~17 providers, including Antigravity and Grok) instead of scraping each
   provider itself.
2. **Topology** — the agent reads it remotely over a private Tailscale
   tailnet, so the agent and the sign-ins can live on different machines.
3. **Purpose** — the output feeds an orchestrator's (e.g. T3 Code's) model
   selection, not a dashboard a human watches.

## Credits

- [OpenTokenUsage](https://www.poweruserz.dev/) by PowerUserZ (MIT) — the
  tray app that collects the quotas and provides the local API this bridge
  relays. This project is a bridge *for* it, not a fork of it.
- [Tailscale](https://tailscale.com/) — private networking (WireGuard-based
  tailnet).
- [Model Context Protocol](https://www.anthropic.com/news/model-context-protocol)
  — the open standard used to hand the data to agents.
- [T3 Code](https://github.com/pingdotgg/t3code) — the orchestrator that
  motivated this bridge.

## License

MIT — see [LICENSE](LICENSE).
