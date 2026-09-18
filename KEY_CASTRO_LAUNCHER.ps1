$ErrorActionPreference = "Stop"
$liveUrl = "https://keycastro.onrender.com/"

try {
    Start-Process $liveUrl
    exit 0
}
catch {
    try { Add-Type -AssemblyName PresentationFramework -ErrorAction SilentlyContinue | Out-Null } catch {}
    try {
        [System.Windows.MessageBox]::Show(
            "Could not open the Key Castro live website.`n`n$liveUrl`n`n" + $_.Exception.Message,
            "Key Castro Website",
            "OK",
            "Error"
        ) | Out-Null
    } catch {}
    exit 1
}
