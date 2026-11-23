# usage-bridge uninstaller for Windows (PowerShell)
# 1) Stops the running server
# 2) Removes the Startup-folder autostart entry
# 3) Deletes the install folder (including token.txt)
#    Default %USERPROFILE%\usage-bridge; if you installed elsewhere,
#    pass the same folder with -Dest <path>.
# No admin rights needed. OpenTokenUsage / Tailscale are NOT removed;
# uninstall them separately via winget or Windows Settings if you want.
param([string]$Dest = (Join-Path $env:USERPROFILE "usage-bridge"))
$ErrorActionPreference = "Continue"
$dest = $Dest

# 1) Stop the server
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*usage_bridge.py*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "Stopped the usage-bridge server (if it was running)."

# 2) Autostart entry
$startupCmd = Join-Path ([Environment]::GetFolderPath("Startup")) "usage-bridge.cmd"
if (Test-Path $startupCmd) { Remove-Item $startupCmd -Force; Write-Host "Removed Startup entry: $startupCmd" }

# 3) Install folder
if (Test-Path $dest) { Remove-Item $dest -Recurse -Force; Write-Host "Removed folder: $dest" }

Write-Host ""
Write-Host "Done. Remaining manual step:"
Write-Host " - Remove the usage-bridge MCP endpoint from your agent's configuration."
Write-Host "OpenTokenUsage and Tailscale were left installed on purpose."
