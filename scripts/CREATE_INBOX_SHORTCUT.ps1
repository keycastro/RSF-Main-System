$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $project "REALTY_SYSTEMS_FOUNDRY_INBOX_LAUNCHER.ps1"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "RSF INBOX.lnk"
$icon = Join-Path $project "REALTY_SYSTEMS_FOUNDRY.ico"

if (-not (Test-Path $launcher)) { throw "Inbox launcher not found: $launcher" }

foreach ($oldName in @("KEY CASTRO INBOX.lnk", "Key Inbox.lnk", "KEY CASTRO Inbox.lnk")) {
    $oldPath = Join-Path $desktop $oldName
    if (Test-Path $oldPath) { Remove-Item -LiteralPath $oldPath -Force }
}

$ws = New-Object -ComObject WScript.Shell
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$sc.WorkingDirectory = $project
$sc.Description = "Open the private Realty Systems Foundry inbox"
if (Test-Path $icon) { $sc.IconLocation = $icon }
$sc.Save()
Write-Host "Desktop shortcut created: $shortcutPath" -ForegroundColor Green
