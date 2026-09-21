$ErrorActionPreference = "SilentlyContinue"
$stopped = $false
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @("python.exe","pythonw.exe") -and $_.CommandLine -and $_.CommandLine -match "run\.py" -and ($_.CommandLine -match "REALTY_SYSTEMS_FOUNDRY" -or $_.CommandLine -match "KEY_CASTRO_WEBSITE")
} | ForEach-Object {
    $processId = $_.ProcessId
    Stop-Process -Id $processId -Force
    Write-Host "Stopped Realty Systems Foundry website process PID $processId." -ForegroundColor Green
    $stopped = $true
}
if (!$stopped) { Write-Host "No Realty Systems Foundry website server was running on port 5050." }
