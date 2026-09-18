$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $project "KEY_CASTRO_INBOX_LAUNCHER.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "KEY CASTRO INBOX.lnk"
$icon = Join-Path $project "KEY_CASTRO.ico"

if (-not (Test-Path $launcher)) { throw "Inbox launcher not found: $launcher" }

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$sc.WorkingDirectory = $project
$sc.Description = "Open the private Key Castro online inbox"
if (Test-Path $icon) { $sc.IconLocation = $icon }
$sc.Save()
Write-Host "Created: $shortcutPath"
