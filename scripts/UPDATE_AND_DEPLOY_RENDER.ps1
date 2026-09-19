$ErrorActionPreference = "Stop"

$packageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$documents = [Environment]::GetFolderPath("MyDocuments")
$target = Join-Path $documents "KEY_CASTRO_WEBSITE"
$serviceId = "srv-dam749e1egvs738cppq0"
$liveBase = "https://keycastro.onrender.com"
$expectedVersion = "3.8.1"
$commitMessage = "Release 3.8.1 How It Works redundancy cleanup"

function Invoke-Native {
    param(
        [Parameter(Mandatory=$true)][string]$Command,
        [string[]]$Arguments = @()
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE."
    }
}

function Get-NativeText {
    param(
        [Parameter(Mandatory=$true)][string]$Command,
        [string[]]$Arguments = @()
    )
    $output = & $Command @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE.`n$($output -join [Environment]::NewLine)"
    }
    if ($null -eq $output) { return "" }
    return (($output -join "`n").Trim())
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  KEY CASTRO - UPDATE + AUTOMATIC LIVE DEPLOY" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This single run will:" -ForegroundColor Gray
Write-Host "  1. update the local website"
Write-Host "  2. preserve private local configuration"
Write-Host "  3. run the full automated test suite"
Write-Host "  4. commit approved website files only"
Write-Host "  5. push the private repo and Render deployment mirror"
Write-Host "  6. trigger the Render deployment"
Write-Host "  7. verify the LIVE website before reporting success"
Write-Host ""

Write-Host "[A/7] Applying the website update and running local tests..." -ForegroundColor Yellow
$installer = Join-Path $packageRoot "scripts\INSTALL_WEBSITE.ps1"
if (!(Test-Path $installer)) { throw "Installer not found: $installer" }
& $installer

if (!(Test-Path $target)) { throw "Installed website folder was not found: $target" }
if (!(Test-Path (Join-Path $target ".git"))) {
    throw "The installed website is not connected to its existing Git repository. Automatic deployment stopped safely."
}

Push-Location $target
try {
    Write-Host "[B/7] Checking Git repository and deployment remotes..." -ForegroundColor Yellow
    $git = Get-Command git.exe -ErrorAction SilentlyContinue
    if (!$git) { $git = Get-Command git -ErrorAction SilentlyContinue }
    if (!$git) { throw "Git was not found. Install Git for Windows or restore the existing Git installation." }

    $branch = Get-NativeText -Command $git.Source -Arguments @("rev-parse", "--abbrev-ref", "HEAD")
    if ($branch -ne "main") {
        throw "Expected Git branch 'main' but found '$branch'. Deployment stopped to avoid publishing the wrong branch."
    }

    # Approved release scope. This is also used to recover safely from a prior
    # updater run that failed after staging release files but before commit.
    $approvedRootDirs = @("app/", "scripts/", "tests/", "docs/")
    $approvedRootFiles = @(
        ".env.example", ".gitignore", "config.py", "run.py", "wsgi.py",
        "requirements.txt", "requirements-production.txt",
        "README.md", "CHANGELOG.md", "DELIVERY_REPORT.md", "RELEASE_AUDIT.md",
        "VERSION.txt", "PROJECT_STATE.json", "DEVELOPER_HANDOFF.md",
        "NEXT_DEVELOPER_READ_THIS_FIRST.md", "SECURITY_AND_SHARING_NOTES.md",
        "KEY_CASTRO_LAUNCHER.ps1", "KEY_CASTRO.ico",
        "START_KEY_CASTRO_WEBSITE.bat", "SETUP_KEY_CASTRO_WEBSITE.bat",
        "STOP_KEY_CASTRO_WEBSITE.bat", "APPLY_UPDATE_AND_DEPLOY_LIVE.bat",
        "AUTO_DEPLOY_README.txt"
    )

    function Test-ApprovedReleasePath {
        param([Parameter(Mandatory=$true)][string]$Name)
        $normalized = $Name.Replace('\','/')
        if ($approvedRootFiles -contains $normalized) { return $true }
        foreach ($prefix in $approvedRootDirs) {
            if ($normalized.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
        }
        return $false
    }

    $preStaged = Get-NativeText -Command $git.Source -Arguments @("diff", "--cached", "--name-only")
    if ($preStaged) {
        $preStagedNames = $preStaged -split "`n" | ForEach-Object { $_.Trim().Replace('\','/') } | Where-Object { $_ }
        $unexpectedStaged = @($preStagedNames | Where-Object { -not (Test-ApprovedReleasePath $_) })
        if ($unexpectedStaged.Count -gt 0) {
            throw "There are pre-existing staged changes outside the approved release scope: $($unexpectedStaged -join ', '). Deployment stopped so unrelated work is not mixed into the release."
        }
        Write-Host "      Recovering approved staged files left by the previous failed updater run..." -ForegroundColor DarkGray
        Invoke-Native -Command $git.Source -Arguments @("reset", "--quiet")
    }

    $remotes = (Get-NativeText -Command $git.Source -Arguments @("remote")) -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ }
    if ($remotes -notcontains "origin") { throw "Git remote 'origin' is missing." }
    if ($remotes -notcontains "renderdeploy") { throw "Git remote 'renderdeploy' is missing." }

    Write-Host "[C/7] Staging only approved website release files..." -ForegroundColor Yellow
    $approvedPaths = @(
        "app", "scripts", "tests", "docs",
        ".env.example", ".gitignore", "config.py", "run.py", "wsgi.py",
        "requirements.txt", "requirements-production.txt",
        "README.md", "CHANGELOG.md", "DELIVERY_REPORT.md", "RELEASE_AUDIT.md",
        "VERSION.txt", "PROJECT_STATE.json", "DEVELOPER_HANDOFF.md",
        "NEXT_DEVELOPER_READ_THIS_FIRST.md", "SECURITY_AND_SHARING_NOTES.md",
        "KEY_CASTRO_LAUNCHER.ps1", "KEY_CASTRO.ico", "START_KEY_CASTRO_WEBSITE.bat",
        "SETUP_KEY_CASTRO_WEBSITE.bat", "STOP_KEY_CASTRO_WEBSITE.bat",
        "APPLY_UPDATE_AND_DEPLOY_LIVE.bat", "AUTO_DEPLOY_README.txt"
    )
    foreach ($path in $approvedPaths) {
        # Respect repository/global ignore rules. Ignored release notes must never
        # stop a live deployment. Tracked ignored files still remain stageable.
        & $git.Source check-ignore -q -- $path 2>$null
        $ignoreExit = $LASTEXITCODE
        if ($ignoreExit -eq 0) {
            Write-Host "      Skipping ignored path: $path" -ForegroundColor DarkGray
            continue
        } elseif ($ignoreExit -ne 1) {
            throw "Could not evaluate Git ignore status for: $path"
        }

        $exists = Test-Path -LiteralPath (Join-Path $target $path)

        # Determine whether Git already tracks this path WITHOUT using
        # --error-unmatch. New approved release files (for example CHANGELOG.md)
        # are valid and must not raise a native stderr error under Windows
        # PowerShell 5.1 with ErrorActionPreference=Stop.
        $trackedOutput = & $git.Source ls-files -- $path 2>$null
        if ($LASTEXITCODE -ne 0) {
            throw "Could not inspect Git tracking status for approved path: $path"
        }
        $tracked = $false
        if ($null -ne $trackedOutput) {
            $trackedLines = @($trackedOutput | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ })
            $tracked = ($trackedLines.Count -gt 0)
        }

        if (-not $exists -and -not $tracked) {
            Write-Host "      Skipping absent untracked path: $path" -ForegroundColor DarkGray
            continue
        }

        & $git.Source add -A -- $path
        if ($LASTEXITCODE -ne 0) { throw "Git staging failed for approved path: $path" }
    }

    $stagedText = Get-NativeText -Command $git.Source -Arguments @("diff", "--cached", "--name-only")
    $stagedNames = @()
    if ($stagedText) { $stagedNames = $stagedText -split "`n" | ForEach-Object { $_.Trim().Replace('\\','/') } | Where-Object { $_ } }

    foreach ($name in $stagedNames) {
        $lower = $name.ToLowerInvariant()
        $forbidden = $false
        if ($lower -eq ".env" -or $lower -eq ".owner_inbox.json") { $forbidden = $true }
        if ($lower -like ".venv/*" -or $lower -like "_backups/*") { $forbidden = $true }
        if ($lower -like "instance/*" -and $lower -ne "instance/.gitkeep") { $forbidden = $true }
        if ($lower -like "logs/*" -and $lower -ne "logs/.gitkeep") { $forbidden = $true }
        if ($lower -match '\.(sqlite|sqlite3|db)$') { $forbidden = $true }
        if ($forbidden) {
            & $git.Source reset --quiet
            throw "Safety stop: private/runtime file would have been staged: $name"
        }
    }

    Invoke-Native -Command $git.Source -Arguments @("diff", "--cached", "--check")

    Write-Host "[D/7] Creating the release commit when needed..." -ForegroundColor Yellow
    & $git.Source diff --cached --quiet
    $diffExit = $LASTEXITCODE
    if ($diffExit -eq 1) {
        Invoke-Native -Command $git.Source -Arguments @("commit", "-m", $commitMessage)
    } elseif ($diffExit -eq 0) {
        Write-Host "      No new commit needed; local main already contains this release." -ForegroundColor DarkGray
    } else {
        throw "Could not determine whether staged changes exist."
    }

    $sha = Get-NativeText -Command $git.Source -Arguments @("rev-parse", "HEAD")
    Write-Host "      Release commit: $sha" -ForegroundColor DarkGray

    Write-Host "[E/7] Pushing GitHub repositories..." -ForegroundColor Yellow
    Invoke-Native -Command $git.Source -Arguments @("push", "origin", "main")
    Invoke-Native -Command $git.Source -Arguments @("push", "renderdeploy", "main")

    Write-Host "[F/7] Triggering Render deployment..." -ForegroundColor Yellow
    $render = Get-Command render.exe -ErrorAction SilentlyContinue
    if (!$render) { $render = Get-Command render -ErrorAction SilentlyContinue }
    if (!$render) {
        throw "Render CLI was not found. The Git pushes succeeded, but the live deployment could not be triggered. Restore the Render CLI and rerun this same updater."
    }
    Invoke-Native -Command $render.Source -Arguments @("deploys", "create", $serviceId, "--wait", "--confirm", "-o", "text")

    Write-Host "[G/7] Verifying the LIVE website..." -ForegroundColor Yellow
    $verified = $false
    $lastError = ""
    for ($attempt = 1; $attempt -le 12; $attempt++) {
        try {
            $stamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            $health = Invoke-RestMethod -Uri "$liveBase/system/health?verify=$stamp" -Method Get -TimeoutSec 30
            $systems = Invoke-WebRequest -Uri "$liveBase/system-templates?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $how = Invoke-WebRequest -Uri "$liveBase/services?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $hasStudentHousing = $systems.Content -match [regex]::Escape("Student Housing Matching and Placement System")
            $systemCardCount = ([regex]::Matches($systems.Content, "data-system-card")).Count
            $hasThreeSystems = $systemCardCount -eq 3
            $hasAdaptSentence = $how.Content -match [regex]::Escape("I can adapt one of my existing systems to fit your business.")
            $hasStep1 = $how.Content -match [regex]::Escape('<div class="human-step-number">1</div>')
            $hasStep2 = $how.Content -match [regex]::Escape('<div class="human-step-number">2</div>')
            $hasNoStep3 = -not ($how.Content -match [regex]::Escape('<div class="human-step-number">3</div>'))
            $oldBuildStepGone = -not ($how.Content -match [regex]::Escape('<h2>I build the system.</h2>'))
            $hasManagementStep = $how.Content -match [regex]::Escape("Choose who manages it.")
            $hasFinalCta = ($how.Content -match [regex]::Escape("Want to get started?")) -and ($how.Content -match [regex]::Escape("Tell Me What You Need"))
            $hasPricing = ($how.Content -match [regex]::Escape('$49/month')) -and ($how.Content -match [regex]::Escape('$490/year'))
            if ($health.status -eq "ok" -and $health.version -eq $expectedVersion -and $hasStudentHousing -and $hasThreeSystems -and $hasAdaptSentence -and $hasStep1 -and $hasStep2 -and $hasNoStep3 -and $oldBuildStepGone -and $hasManagementStep -and $hasFinalCta -and $hasPricing) {
                $verified = $true
                break
            }
            $lastError = "Health/version/How It Works/Systems content has not refreshed yet."
        }
        catch {
            $lastError = $_.Exception.Message
        }
        if ($attempt -lt 12) {
            Write-Host "      Live verification attempt $attempt/12 not ready yet; retrying..." -ForegroundColor DarkGray
            Start-Sleep -Seconds 10
        }
    }

    if (!$verified) {
        throw "Render deployment command completed, but live verification failed after retries. Last result: $lastError"
    }

    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  LIVE DEPLOYMENT VERIFIED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "Version: $expectedVersion"
    Write-Host "Live site: $liveBase"
    Write-Host "Systems: 3 published systems confirmed"
    Write-Host "Student Housing system: confirmed LIVE"
    Write-Host "Commit: $sha"
    Write-Host ""
}
finally {
    Pop-Location
}
