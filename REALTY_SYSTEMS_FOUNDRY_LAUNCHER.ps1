$ErrorActionPreference = "Stop"
$newLiveUrl = "https://realtysystemsfoundry.onrender.com/"
$legacyLiveUrl = "https://keycastro.onrender.com/"
$liveUrl = $newLiveUrl

try {
    $health = Invoke-RestMethod -Uri ($newLiveUrl.TrimEnd('/') + "/system/health") -Method Get -TimeoutSec 8
    if ($health.status -ne "ok" -or $health.app -ne "Realty Systems Foundry") {
        $liveUrl = $legacyLiveUrl
    }
}
catch {
    # Temporary safety fallback only if the Render rename has not completed yet.
    $liveUrl = $legacyLiveUrl
}

try {
    Start-Process $liveUrl
    exit 0
}
catch {
    try { Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue | Out-Null } catch {}
    try {
        [System.Windows.MessageBox]::Show(
            "Could not open the Realty Systems Foundry live website.`n`n$liveUrl`n`n" + $_.Exception.Message,
            "Realty Systems Foundry",
            "OK",
            "Error"
        ) | Out-Null
    } catch {}
    exit 1
}
