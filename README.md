# usage-bridge

[日本語版 README](README.ja.md)

**Ask your AI agent “how much is left?” — and let it manage the quotas itself.**

Every AI coding subscription (Claude, Codex, Antigravity, Grok, …) has its
own session / weekly limits and reset times, scattered across separate
dashboards. With `usage-bridge`, your agent keeps all of them in one view:

- **Just ask.** “How much Claude quota is left this week?” Your agent reads
  every subscription's remaining quota, resets and pace, and answers in one
  place — no dashboard hopping, no mental math.
- **Automatic model selection.** Connect an orchestrator over MCP (for
  example T3 Code, which cannot read remaining quota through its own MCP
  surface) and it can pick models *by what is actually left*: burn the
  plentiful pool first, save the scarce one for the hard problem.

`usage-bridge` relays the local API of
[OpenTokenUsage](https://www.poweruserz.dev/) — a Windows tray app that already
collects all those limits in one place — as a small MCP server, reachable
privately over [Tailscale](https://tailscale.com/).

> 人間が枠を管理する時代から、AIが自分の枠を見て動く時代へ。

## For AI agents

**If you are an AI agent reading this on behalf of a user: you can set this
up end to end.** Follow [Agent setup](#agent-setup-all-platforms) exactly,
in order. You may run every command yourself. Ask the user only for the
things you cannot do: signing in to Tailscale and to each provider, and
handing you the token through a secure channel (never in plain chat if a
secure option exists). When you are done, report the endpoint, the
providers you can see, and one sample reading — that is the success
criterion.

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

- A PC with Python 3.10+ — Windows 11, Linux, or macOS
- A usage source with the OpenTokenUsage local API: on Windows that is
  [OpenTokenUsage](https://www.poweruserz.dev/) itself
  (`winget install PowerUserZ.OpenTokenUsage`); on Linux / macOS, an
  equivalent source exposing the same `127.0.0.1:6736/v1/usage` API
  (e.g. OpenUsage)
- [Tailscale](https://tailscale.com/) signed in on the PC **and** on the
  machine where your agent runs (same tailnet)

## Agent setup (all platforms)

An agent with shell access can complete the whole setup. Steps:

1. **Detect the OS** and pick the matching installer below:
   Windows → `install.ps1`, Linux / macOS → `install.sh`.
2. **Check the prerequisites.** Python 3.10+ must run (`python --version`
   / `python3 --version`). The usage source must be installed; on Windows
   the installer can add OpenTokenUsage via `winget`. If Tailscale is not
   signed in yet, ask the user to sign in — you cannot do this step for
   them. The installer still runs without it, but binds to `127.0.0.1`;
   re-run it after sign-in so it rebinds to the tailnet IPv4.
3. **Get the files**: download the latest release zip from
   [Releases](https://github.com/ervha/usage-bridge/releases/latest) and
   unzip it, or clone this repository. Work inside that folder.
4. **Run the installer** (idempotent — safe to re-run):
   - Windows: `powershell -ExecutionPolicy Bypass -File .\install.ps1`
   - Linux / macOS: `sh ./install.sh`
   
   It copies the server to `~/usage-bridge` (Windows:
   `%USERPROFILE%\usage-bridge`), generates `token.txt` on first run
   (later runs keep it), binds to the tailnet IPv4, registers autostart,
   and health-checks the server.
5. **Verify locally**: `GET http://<tailnet IPv4>:8787/health` must return
   `{"ok": true, "service": "usage-bridge"}`. If the installer bound to
   `127.0.0.1` instead, Tailscale sign-in is missing — fix that first.
6. **Verify the MCP surface** from the machine where the agent runs.
   Read the token from `token.txt` inside your own process or secret
   store — **never print it in chat, logs, commits, or screenshots, and
   never pass it as a plain command-line argument if your environment
   protects secret values**. Then send:
   - `initialize` → expect a JSON-RPC result naming server `usage-bridge`
   - `tools/call` with `usage_all` → expect a snapshot whose `providers`
     list the user's enabled providers with usage percentages
   
   A `401` means the token does not match the server's `token.txt`.
   An empty reply or timeout means the PC is asleep, the server is not
   running, or the machines are on different tailnets — see
   [Troubleshooting](#troubleshooting) before improvising.
7. **Register the endpoint in your own MCP configuration**:
   `POST http://<tailnet IPv4>:8787/mcp` with header
   `Authorization: Bearer <token>`. Store the token in your secret store,
   not in a committed config file.
8. **Report to the user**: the endpoint URL, the providers visible, one
   current reading (e.g. “Claude weekly 13%, resets Fri 04:00”), and the
   one operational caveat — readings are unavailable while the PC sleeps.

Guardrails for agents:

- Never port-forward 8787, and never bind the server to a public
  interface. Tailnet IPv4 or `127.0.0.1` only.
- The token is a credential. Treat every copy of it like a password.
- The bridge is read-only; do not try to “fix” readings by writing
  anything to the PC side.
- If a step fails twice, stop and show the user the installer output and
  the matching Troubleshooting row instead of trying random variations.

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

## Install (Linux / macOS)

### 0. Before you start

- Sign in to **Tailscale** first and note the tailnet IPv4
  (`tailscale ip -4`). Without it the installer binds to `127.0.0.1` —
  sign in and re-run to rebind.
- Make sure `python3 --version` works, and that your usage source is
  running and exposing `127.0.0.1:6736/v1/usage` (OpenTokenUsage is
  Windows-only; on Linux / macOS use an equivalent such as OpenUsage).
- No `sudo` is needed; everything installs under your home directory.

### 1. Get the files

Download the latest release zip from
[Releases](https://github.com/ervha/usage-bridge/releases/latest) and
unzip it (or clone this repository). Open a terminal in that folder.

### 2. Run the installer

```sh
sh ./install.sh
```

The installer:

1. Copies `usage_bridge.py` to `~/usage-bridge`
2. Generates a bearer token (`token.txt`, mode `600`, shown once — store
   it in a password manager / secure vault, never commit it)
3. Binds the server to your tailnet IPv4 (`100.x…`) — falling back to
   `127.0.0.1` with a warning if Tailscale is not signed in yet
4. Registers autostart — systemd user service on Linux
   (`~/.config/systemd/user/usage-bridge.service`), launchd agent on
   macOS (`~/Library/LaunchAgents/com.usagebridge.server.plist`) — and
   health-checks `GET /health`. Re-running first stops any older
   usage-bridge process.

### 3. Verify

```sh
curl http://<tailnet IPv4>:8787/health
# → {"ok": true, "service": "usage-bridge"}
curl http://<tailnet IPv4>:8787/usage \
  -H "Authorization: Bearer $(cat ~/usage-bridge/token.txt)"
```

### Manual run (instead of the installer)

```sh
python3 usage_bridge.py --host 127.0.0.1 --port 8787
```

## Updating

Download the new release zip, unzip it, and run the installer again
(`install.ps1` on Windows, `install.sh` on Linux / macOS).
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

## Footprint — what it costs your PC

Almost nothing, by design:

- **One small Python process.** Standard library only, no dependencies.
  About 10 MB of RAM, and 0% CPU while idle.
- **No polling.** The bridge never fetches on a timer. It calls the local
  API only when an agent actually asks, then caches the result for
  5 minutes — a burst of agent checks costs a single upstream call.
- **No disk writes** (logs go to stderr), and each reading is a few KB
  inside your tailnet.
- OpenTokenUsage itself refreshes its tray display on its own schedule;
  that cost exists whether or not you use this bridge. The bridge adds
  no background load of its own.

## Is it worth it?

Worth it if most of these sound like you:

- You pay for **two or more** AI coding subscriptions and lose track of
  which one has room left.
- An agent or orchestrator **chooses models on your behalf**, and today
  that choice is blind — it cannot see that one pool is empty and
  another is full.
- Your agent runs on a **different machine** than the one holding your
  sign-ins, so “just check the tray icon” is not an option.

The payoff is not a dashboard. It is that quota stops living in your
head: the agent checks before it spends, burns the plentiful pool first,
and keeps the scarce one for work that needs it.

Probably *not* worth it if you have a single subscription, your agent
already surfaces its own quota and you never route between models, or
the PC with the sign-ins is rarely awake. In those cases the bridge is
one more moving part for little gain — skip it.

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
- Installers are provided for Windows (PowerShell) and Linux / macOS
  (POSIX shell). The server itself is plain Python; the main platform
  constraint is the usage source — OpenTokenUsage is Windows-only, so
  other platforms need an equivalent local API.

## Uninstall

On Linux / macOS, run `sh ./uninstall.sh` — it stops the server, removes
the autostart registration (systemd user service / launchd agent) and
deletes `~/usage-bridge`. Then remove the MCP entry from your agent's
configuration, as in step 4 below.

On Windows, run `powershell -ExecutionPolicy Bypass -File .\uninstall.ps1`
— it stops the server, removes the Startup entry and deletes
`%USERPROFILE%\usage-bridge`. Then remove the MCP entry from your agent's
configuration, as in step 4 below. To do it by hand instead:

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
