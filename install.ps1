# usage-bridge installer for your PC (Windows 11, PowerShell)
# 1) Installs OpenTokenUsage if missing (winget)
# 2) Copies usage_bridge.py to %USERPROFILE%\usage-bridge
# 3) Generates a bearer token (token.txt, shown once at the end — send it to your AI agent)
# 4) Registers logon autostart via Task Scheduler
# 5) Starts the server and checks /health
$ErrorActionPreference = "Stop"
$dest = Join-Path $env:USERPROFILE "usage-bridge"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

# 1) OpenTokenUsage
$otu = Get-Command OpenTokenUsage -ErrorAction SilentlyContinue
if (-not $otu) {
  Write-Host "Installing OpenTokenUsage via winget..."
  winget install --id PowerUserZ.OpenTokenUsage -e --accept-source-agreements --accept-package-agreements
} else { Write-Host "OpenTokenUsage already present." }

# 2) Server file
Copy-Item (Join-Path $PSScriptRoot "usage_bridge.py") (Join-Path $dest "usage_bridge.py") -Force

# 3) Token
$tokenFile = Join-Path $dest "token.txt"
if (-not (Test-Path $tokenFile)) {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $token = [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+","-").Replace("/","_")
  Set-Content -Path $tokenFile -Value $token -Encoding ascii
  Write-Host "Generated token: $token"
  Write-Host "IMPORTANT: send this token to your AI agent (store it in a secure vault)."
} else { Write-Host "Token already exists at $tokenFile (unchanged)." }

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
$py = (Get-Command python).Source
if (-not $py) { $py = (Get-Command py).Source }
$action = New-ScheduledTaskAction -Execute $py -Argument "`"$dest\usage_bridge.py`" --port 8787 --host $bindHost" -WorkingDirectory $dest
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "usage-bridge" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Write-Host "Registered Task Scheduler job 'usage-bridge' (starts at logon)."

# 5) Start now + health check
Start-ScheduledTask -TaskName "usage-bridge"
Start-Sleep -Seconds 3
try {
  $h = Invoke-RestMethod -Uri "http://127.0.0.1:8787/health" -TimeoutSec 5
  Write-Host "usage-bridge health: $($h | ConvertTo-Json -Compress)"
} catch { Write-Warning "Health check failed: $_  (check that Python is installed and port 8787 is free)" }

Write-Host ""
Write-Host "Next steps:"
Write-Host " 1) Open OpenTokenUsage once and sign in / enable the providers you use (Claude, Codex, Antigravity, Grok)."
Write-Host " 2) Make sure Tailscale is signed in on this PC (same account as your agent's VM)."
Write-Host " 3) Tell your AI agent this PC's tailnet IPv4 (run: tailscale ip -4) and the token above."
