$ErrorActionPreference = "Stop"

$source = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$documents = [Environment]::GetFolderPath("MyDocuments")
$target = Join-Path $documents "KEY_CASTRO_WEBSITE"

Write-Host ""
Write-Host "KEY CASTRO WEBSITE - ONE-TIME SETUP" -ForegroundColor Cyan
Write-Host "Install location: $target"
Write-Host ""

if (!(Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }

$sourceFull = [System.IO.Path]::GetFullPath($source).TrimEnd('\')
$targetFull = [System.IO.Path]::GetFullPath($target).TrimEnd('\')

if ($sourceFull -ne $targetFull) {
    Write-Host "[1/7] Copying website files into Documents..."
    foreach ($dir in @("app", "scripts", "tests", "docs")) {
        $srcDir = Join-Path $source $dir
        $dstDir = Join-Path $target $dir
        if (Test-Path $dstDir) { Remove-Item $dstDir -Recurse -Force }
        if (Test-Path $srcDir) { Copy-Item $srcDir $dstDir -Recurse -Force }
    }
    $files = @(
        ".env.example", ".gitignore", "config.py", "run.py", "wsgi.py", "requirements.txt",
        "requirements-production.txt", "README.md", "DELIVERY_REPORT.md", "VERSION.txt", "KEY_CASTRO_LAUNCHER.ps1",
        "KEY_CASTRO.ico", "START_KEY_CASTRO_WEBSITE.bat", "SETUP_KEY_CASTRO_WEBSITE.bat",
        "STOP_KEY_CASTRO_WEBSITE.bat"
    )
    foreach ($file in $files) {
        $srcFile = Join-Path $source $file
        if (Test-Path $srcFile) { Copy-Item $srcFile (Join-Path $target $file) -Force }
    }
} else {
    Write-Host "[1/7] Website is already inside Documents."
}

foreach ($dir in @("logs", "instance")) {
    $path = Join-Path $target $dir
    if (!(Test-Path $path)) { New-Item -ItemType Directory -Path $path -Force | Out-Null }
}

Push-Location $target
try {
    Write-Host "[2/7] Checking Python..."
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    $pythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
    if (!$py -and !$pythonCmd) { throw "Python was not found. Install Python 3.10+ from python.org and enable 'Add Python to PATH'." }

    if ($py) {
        $versionText = & $py.Source -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    } else {
        $versionText = & $pythonCmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    }
    $parts = $versionText.Trim().Split('.')
    if ([int]$parts[0] -lt 3 -or ([int]$parts[0] -eq 3 -and [int]$parts[1] -lt 10)) { throw "Python 3.10 or newer is required. Found $versionText." }
    Write-Host "      Python $versionText detected." -ForegroundColor DarkGray

    Write-Host "[3/7] Creating isolated Python environment..."
    $venvPython = Join-Path $target ".venv\Scripts\python.exe"
    if (!(Test-Path $venvPython)) {
        if ($py) { & $py.Source -3 -m venv ".venv" } else { & $pythonCmd.Source -m venv ".venv" }
        if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
    }

    Write-Host "[4/7] Installing required packages..."
    & $venvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
    & $venvPython -m pip install -r "requirements.txt"
    if ($LASTEXITCODE -ne 0) { throw "Package installation failed. Check your Internet connection and retry setup." }

    Write-Host "[5/7] Preparing local configuration..."
    $envFile = Join-Path $target ".env"
    if (!(Test-Path $envFile)) {
        $secret = & $venvPython -c "import secrets; print(secrets.token_hex(32))"
        $template = Get-Content (Join-Path $target ".env.example") -Raw
        $template = $template.Replace("SECRET_KEY=REPLACE_WITH_A_RANDOM_SECRET", "SECRET_KEY=$secret")
        Set-Content -Path $envFile -Value $template -Encoding UTF8
        Write-Host "      Created private .env configuration." -ForegroundColor DarkGray
    } else {
        Write-Host "      Existing .env preserved." -ForegroundColor DarkGray
    }

    Write-Host "[6/7] Testing the website..."
    & $venvPython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "Website tests failed. Setup stopped before creating the shortcut." }

    Write-Host "[7/7] Creating desktop icon..."
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $target "scripts\CREATE_DESKTOP_SHORTCUT.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Desktop shortcut creation failed." }

    Write-Host ""
    Write-Host "SETUP COMPLETE." -ForegroundColor Green
    Write-Host "Installed in: $target"
    Write-Host "Local URL: http://127.0.0.1:5050"
    Write-Host "From now on, double-click the 'KEY CASTRO' icon on your Desktop."
    Write-Host ""

    Start-Process powershell.exe -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
        "-File", ('"' + (Join-Path $target "KEY_CASTRO_LAUNCHER.ps1") + '"')
    )
}
finally {
    Pop-Location
}
