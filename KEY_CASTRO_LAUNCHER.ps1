$ErrorActionPreference = "Stop"

$project = $PSScriptRoot
$appUrl = "http://127.0.0.1:5050/"
$healthUrl = "http://127.0.0.1:5050/system/health"
$python = Join-Path $project ".venv\Scripts\python.exe"
$server = Join-Path $project "run.py"
$logDir = Join-Path $project "logs"
$logFile = Join-Path $logDir "launcher.log"
$serverStdout = Join-Path $logDir "server_stdout.log"
$serverStderr = Join-Path $logDir "server_stderr.log"

if (!(Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-LaunchLog([string]$Text) {
    try {
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -Path $logFile -Value ("[{0}] {1}" -f $stamp, $Text) -Encoding UTF8
    } catch {}
}

function Show-LaunchError([string]$Text) {
    try { Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue | Out-Null } catch {}
    try { [System.Windows.MessageBox]::Show($Text, "Key Castro Website", "OK", "Error") | Out-Null } catch {}
}

function Test-KeyCastroWebsite {
    try {
        $r = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        return ($r.status -eq "ok" -and $r.app -eq "Key Castro Portfolio")
    } catch { return $false }
}

function Test-IsWebsiteProcess($ProcessInfo) {
    if (!$ProcessInfo) { return $false }
    if ($ProcessInfo.Name -notin @("python.exe", "pythonw.exe")) { return $false }
    if (!$ProcessInfo.CommandLine) { return $false }
    $cmd = $ProcessInfo.CommandLine
    $looksLikeRun = $cmd.IndexOf("run.py", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    $looksLikeProject = $cmd.IndexOf("KEY_CASTRO_WEBSITE", [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    return ($looksLikeRun -and $looksLikeProject)
}

function Stop-StaleWebsiteServer {
    $listeners = @(Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue)
    if ($listeners.Count -eq 0) { return }
    if (Test-KeyCastroWebsite) { return }

    $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($processId in $pids) {
        $processInfo = Get-CimInstance Win32_Process -Filter ("ProcessId={0}" -f $processId) -ErrorAction SilentlyContinue
        if (!(Test-IsWebsiteProcess $processInfo)) {
            throw "Port 5050 is being used by another program. The launcher did not stop it for safety."
        }
        Write-LaunchLog ("Stopping stale Key Castro website process PID {0}." -f $processId)
        Stop-Process -Id $processId -Force -ErrorAction Stop
    }

    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 250
        if (@(Get-NetTCPConnection -LocalPort 5050 -State Listen -ErrorAction SilentlyContinue).Count -eq 0) { return }
    }
    throw "The old website server did not release port 5050 in time."
}

try {
    if (!(Test-Path $python)) { throw "Website is not installed yet. Run SETUP_KEY_CASTRO_WEBSITE.bat once." }
    if (!(Test-Path $server)) { throw "Website server file not found: $server" }

    if (Test-KeyCastroWebsite) {
        Write-LaunchLog "Website is already running. Opening browser only."
        Start-Process $appUrl
        exit 0
    }

    Stop-StaleWebsiteServer
    Remove-Item $serverStdout,$serverStderr -Force -ErrorAction SilentlyContinue
    Write-LaunchLog "Starting Key Castro local website."

    Start-Process -FilePath $python `
        -ArgumentList ('"{0}"' -f $server) `
        -WorkingDirectory $project `
        -WindowStyle Hidden `
        -RedirectStandardOutput $serverStdout `
        -RedirectStandardError $serverStderr

    $ready = $false
    for ($i = 0; $i -lt 50; $i++) {
        Start-Sleep -Milliseconds 400
        if (Test-KeyCastroWebsite) { $ready = $true; break }
    }

    if (!$ready) {
        if (Test-Path $serverStderr) {
            try {
                $tail = (Get-Content -LiteralPath $serverStderr -Tail 40 -ErrorAction SilentlyContinue) -join " | "
                if ($tail) { Write-LaunchLog ("SERVER STARTUP ERROR: " + $tail) }
            } catch {}
        }
        throw "Website did not become ready on 127.0.0.1:5050."
    }

    Write-LaunchLog "Health check passed. Opening browser."
    Start-Process $appUrl
}
catch {
    $message = $_.Exception.Message
    Write-LaunchLog ("ERROR: " + $message)
    Show-LaunchError ("Key Castro Website could not open.`n`n" + $message + "`n`nLog:`n" + $logFile)
    exit 1
}
