$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$configPath = Join-Path $root ".owner_inbox.json"

try {
    if (-not (Test-Path $configPath)) {
        throw "Private inbox configuration is missing. Run the website inbox merge installer again."
    }

    $cfg = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if (-not $cfg.api_base -or -not $cfg.token) {
        throw "Private inbox configuration is incomplete."
    }

    $headers = @{
        Authorization = "Bearer $($cfg.token)"
        Accept = "application/json"
    }

    $ticket = Invoke-RestMethod -Method Post -Uri "$($cfg.api_base.TrimEnd('/'))/session-ticket" -Headers $headers -TimeoutSec 20
    if (-not $ticket.url) {
        throw "The live website did not return a private inbox access link."
    }

    Start-Process $ticket.url
    exit 0
}
catch {
    try { Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue | Out-Null } catch {}
    try {
        [System.Windows.MessageBox]::Show(
            "Could not open the private REALTY SYSTEMS FOUNDRY INBOX.`n`n" + $_.Exception.Message,
            "RSF INBOX",
            "OK",
            "Error"
        ) | Out-Null
    } catch {}
    exit 1
}
