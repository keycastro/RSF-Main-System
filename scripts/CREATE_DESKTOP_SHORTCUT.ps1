$ErrorActionPreference = "Stop"

$project = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$launcher = Join-Path $project "REALTY_SYSTEMS_FOUNDRY_LAUNCHER.ps1"
$icon = Join-Path $project "REALTY_SYSTEMS_FOUNDRY.ico"

if (!(Test-Path $launcher)) { throw "Launcher not found: $launcher" }
if (!(Test-Path $icon)) { throw "Icon not found: $icon" }

$desktop = [Environment]::GetFolderPath("Desktop")
foreach ($oldName in @("KEY CASTRO.lnk", "Key Castro.lnk")) {
    $oldPath = Join-Path $desktop $oldName
    if (Test-Path $oldPath) { Remove-Item -LiteralPath $oldPath -Force }
}

$shortcut = Join-Path $desktop "REALTY SYSTEMS FOUNDRY.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($shortcut)
$s.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$s.Arguments = '-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $launcher + '"'
$s.WorkingDirectory = $project
$s.IconLocation = $icon + ",0"
$s.Description = "Open the Realty Systems Foundry live website"
$s.Save()

Write-Host "Desktop shortcut created: $shortcut" -ForegroundColor Green
