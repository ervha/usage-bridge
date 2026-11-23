# usage-bridge installer for your PC (Windows 11, PowerShell)
# 1) Installs OpenTokenUsage if missing (winget)
# 2) Copies usage_bridge.py to the install folder
#    (default %USERPROFILE%\usage-bridge; choose another with -Dest <path>)
# 3) Creates the bearer token in OS secure storage (Windows DPAPI;
#    the token itself is never printed — hand it over with pairing)
# 4) Registers logon autostart via the Startup folder (no admin rights needed)
# 5) Starts the server and checks /health
param([string]$Dest = (Join-Path $env:USERPROFILE "usage-bridge"))
$ErrorActionPreference = "Stop"
$dest = $Dest
Write-Host "Installing usage-bridge to $dest"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

# 1) OpenTokenUsage
$otu = Get-Command OpenTokenUsage -ErrorAction SilentlyContinue
if (-not $otu) {
  Write-Host "Installing OpenTokenUsage via winget..."
  winget install --id PowerUserZ.OpenTokenUsage -e --accept-source-agreements --accept-package-agreements
} else { Write-Host "OpenTokenUsage already present." }

# 2) Server file
Copy-Item (Join-Path $PSScriptRoot "usage_bridge.py") (Join-Path $dest "usage_bridge.py") -Force

# 3) Token — created (or migrated from an old token.txt) by the server
#    itself, into OS secure storage. The token is never printed.
$pyInit = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pyInit) { $pyInit = (Get-Command py -ErrorAction SilentlyContinue).Source }
if ($pyInit) {
  & $pyInit (Join-Path $dest "usage_bridge.py") --init-token
} else {
  Write-Warning "Python not found yet; after installing it, run  python `"$dest\usage_bridge.py`" --init-token"
}

# 4) Autostart (at logon). Tunnel is Tailscale (decided 2026-11-23):
#    bind the server to this PC's tailnet IPv4 so your agent's VM can reach it
#    through the tailnet. Falls back to 127.0.0.1 if Tailscale is not signed in yet.
$ts = Get-Command tailscale -ErrorAction SilentlyContinue
if (-not $ts) {
  Write-Host "Installing Tailscale via winget..."
  winget install --id Tailscale.Tailscale -e --accept-source-agreements --accept-package-agreements
  $ts = Get-Command tailscale -ErrorAction SilentlyContinue
}
$bindHost = "127.0.0.1"
if ($ts) {
  $ip4 = (& $ts.Source ip -4 2>$null | Select-Object -First 1)
  if ($ip4 -match "^100\.") { $bindHost = $ip4.Trim() }
}
if ($bindHost -eq "127.0.0.1") {
  Write-Warning "Tailscale IPv4 not found. The server will listen on 127.0.0.1 only."
  Write-Warning "Sign in to Tailscale, then re-run this script so it rebinds to the tailnet address."
} else { Write-Host "Binding usage-bridge to tailnet address $bindHost" }
$py = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python).Source }
if (-not $py) { $py = (Get-Command py).Source }
# Autostart via the user's Startup folder (no admin rights needed;
# Task Scheduler registration requires elevation and is not used).
$launcher = Join-Path $dest "start-usage-bridge.cmd"
@"
@echo off
cd /d "$dest"
start "" /min "$py" "$dest\usage_bridge.py" --port 8787 --host $bindHost
"@ | Set-Content -Path $launcher -Encoding ascii
$startup = [Environment]::GetFolderPath("Startup")
Copy-Item $launcher (Join-Path $startup "usage-bridge.cmd") -Force
Write-Host "Registered autostart in the Startup folder (starts at logon, no admin needed)."

# 5) Start now + health check (stop any older usage-bridge process first,
#    otherwise the old one keeps holding port 8787)
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*usage_bridge.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
& $launcher
Start-Sleep -Seconds 3
try {
  $h = Invoke-RestMethod -Uri "http://${bindHost}:8787/health" -TimeoutSec 5
  Write-Host "usage-bridge health: $($h | ConvertTo-Json -Compress)"
} catch { Write-Warning "Health check failed: $_  (check that Python is installed and port 8787 is free)" }

Write-Host ""
Write-Host "Next steps:"
Write-Host " 1) Open OpenTokenUsage once and sign in / enable the providers you use (Claude, Codex, Antigravity, Grok)."
Write-Host " 2) Make sure Tailscale is signed in on this PC (same account as your agent's VM)."
Write-Host " 3) Hand the token over securely: run  python `"$dest\usage_bridge.py`" --pair  and give your agent the 8-character pairing code (valid 10 minutes, single use) plus this PC's tailnet IPv4 (tailscale ip -4). The agent redeems the code for the token, so the token itself never travels."
