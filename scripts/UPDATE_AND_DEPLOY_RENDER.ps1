$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Write-Host "RSF v1.18.229 safe deployment workflow"
Write-Host "Source updates must be merged through GitHub PR/CI before deployment."
$python = Join-Path $root ".venv\Scripts\python.exe"
$script = Join-Path $root "scripts\deploy_render_unified.py"
if (Test-Path $python) {
    & $python $script
} else {
    python $script
}
exit $LASTEXITCODE
