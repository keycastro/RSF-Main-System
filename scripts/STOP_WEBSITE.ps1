$ErrorActionPreference = "Stop"
$stopped = $false
$listeners = @(Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue)
foreach ($listener in $listeners) {
    $processId = $listener.OwningProcess
    $p = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $processId) -ErrorAction SilentlyContinue
    if ($p -and $p.Name -in @("python.exe","pythonw.exe") -and $p.CommandLine -and $p.CommandLine -match "run\.py" -and $p.CommandLine -match "KEY_CASTRO_WEBSITE") {
        Stop-Process -Id $processId -Force
        Write-Host "Stopped Key Castro website process PID $processId." -ForegroundColor Green
        $stopped = $true
    }
}
if (!$stopped) { Write-Host "No Key Castro website server was running on port 5050." }
