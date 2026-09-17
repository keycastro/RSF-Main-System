$ErrorActionPreference = "Stop"

$project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $project "KEY_CASTRO_LAUNCHER.ps1"
$icon = Join-Path $project "KEY_CASTRO.ico"

if (!(Test-Path $launcher)) { throw "Launcher not found: $launcher" }
if (!(Test-Path $icon)) { throw "Icon not found: $icon" }

$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = Join-Path $desktop "KEY CASTRO.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($shortcut)
$s.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$s.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$s.WorkingDirectory = $project
$s.IconLocation = $icon + ",0"
$s.Description = "Open Key Castro professional website"
$s.Save()

Write-Host "Desktop shortcut created: $shortcut" -ForegroundColor Green
