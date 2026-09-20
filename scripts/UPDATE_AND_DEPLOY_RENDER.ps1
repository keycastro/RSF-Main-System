$ErrorActionPreference = "Stop"

$packageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$documents = [Environment]::GetFolderPath("MyDocuments")
$target = Join-Path $documents "KEY_CASTRO_WEBSITE"
$serviceId = "srv-dam749e1egvs738cppq0"
$liveBase = "https://keycastro.onrender.com"
$expectedVersion = "3.8.17"
$commitMessage = "Release 3.8.17 Home CTA Balance Fix"

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
        "00_FUTURE_DEVELOPER_READ_THIS_PLAN.md",
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
        "00_FUTURE_DEVELOPER_READ_THIS_PLAN.md",
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
            $homePage = Invoke-WebRequest -Uri "$liveBase/?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $systems = Invoke-WebRequest -Uri "$liveBase/system-templates?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $detail = Invoke-WebRequest -Uri "$liveBase/system-templates/property-operations-command-center?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $how = Invoke-WebRequest -Uri "$liveBase/services?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $about = Invoke-WebRequest -Uri "$liveBase/about?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $portrait = Invoke-WebRequest -Uri "$liveBase/static/images/about/key-castro.png?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $siteCss = Invoke-WebRequest -Uri "$liveBase/static/css/style.css?verify=$stamp" -UseBasicParsing -TimeoutSec 30
            $hasStudentHousing = $systems.Content -match [regex]::Escape("Student Housing Matching and Placement System")
            $systemCardCount = ([regex]::Matches($systems.Content, "data-system-card")).Count
            $hasThreeSystems = $systemCardCount -eq 3
            $hasStep1 = $how.Content -match [regex]::Escape('<div class="human-step-number">1</div>')
            $hasStep2 = $how.Content -match [regex]::Escape('<div class="human-step-number">2</div>')
            $hasNoStep3 = -not ($how.Content -match [regex]::Escape('<div class="human-step-number">3</div>'))
            $oldBuildStepGone = -not ($how.Content -match [regex]::Escape('<h2>I build the system.</h2>'))
            $hasManagementStep = $how.Content -match [regex]::Escape("Choose who manages it.")
            $hasViewSystemsButton = ($how.Content -match [regex]::Escape('href="/system-templates"')) -and ($how.Content -match [regex]::Escape('>View Systems</a>'))
            $hasRequestSystemButton = ($how.Content -match [regex]::Escape('href="/contact?intent=custom-build"')) -and ($how.Content -match [regex]::Escape('>Request a System</a>'))
            $finalCtaGone = -not ($how.Content -match [regex]::Escape("Want to get started?"))
            $hasExistingSystemPrice = ($homePage.Content -match [regex]::Escape('$160')) -and ($systems.Content -match [regex]::Escape('$160')) -and ($detail.Content -match [regex]::Escape('$160')) -and ($how.Content -match [regex]::Escape('$160'))
            $hasThreeHomePriceCards = (([regex]::Matches($homePage.Content, 'class="existing-system-card-price"')).Count -eq 3)
            $hasThreePricedSystemCards = (([regex]::Matches($systems.Content, 'class="existing-system-card-price"')).Count -eq 3)
            $hasPurchaseBoundary = ($systems.Content -match [regex]::Escape('Changes are priced separately.')) -and ($detail.Content -match [regex]::Escape('This price is for the existing system shown here. Changes are priced separately.')) -and ($how.Content -match [regex]::Escape('If you want changes later, upgrades are priced separately.'))
            $hasExistingSystemContact = ($detail.Content -match [regex]::Escape('intent=existing-system')) -and ($detail.Content -match [regex]::Escape('>Get This System</a>'))
            $hasAgreementPrice = ($how.Content -match [regex]::Escape('BUILD A NEW SYSTEM')) -and ($how.Content -match [regex]::Escape('Price by Agreement')) -and ($how.Content -match [regex]::Escape('Based on the work needed'))
            $oldExistingQuoteGone = -not ($how.Content -match [regex]::Escape('Custom Quote')) -and -not ($how.Content -match [regex]::Escape('The price is a custom quote based on what you need.')) -and -not ($how.Content -match [regex]::Escape('I can adapt one of my existing systems to fit your business.'))
            $hasPricing = ($how.Content -match [regex]::Escape('$39/month')) -and ($how.Content -match [regex]::Escape('$390/year'))
            $oldPricingGone = -not ($how.Content -match [regex]::Escape('$49/month')) -and -not ($how.Content -match [regex]::Escape('$490/year'))
            $pesoSymbol = [char]0x20B1
            $combinedPublicPricingPages = $homePage.Content + $systems.Content + $detail.Content + $how.Content
            $hasUsdOnlyPublicPricing = -not ($combinedPublicPricingPages -match [regex]::Escape($pesoSymbol)) -and -not ($combinedPublicPricingPages -match 'PHP') -and -not ($combinedPublicPricingPages -match 'Philippine peso')
            $hasMaintenanceBoundary = ($how.Content -match [regex]::Escape('Same maintenance service. Choose monthly or yearly billing.')) -and ($how.Content -match [regex]::Escape('Maintenance can include:')) -and ($how.Content -match [regex]::Escape('Hosting and deployment')) -and ($how.Content -match [regex]::Escape('Technical fixes for the current system')) -and ($how.Content -match [regex]::Escape('Maintenance does not include:')) -and ($how.Content -match [regex]::Escape('New features')) -and ($how.Content -match [regex]::Escape('Workflow changes')) -and ($how.Content -match [regex]::Escape('Connections to other tools'))
            $hasUpgradePricing = ($how.Content -match [regex]::Escape('Minor System Upgrade')) -and ($how.Content -match [regex]::Escape('$79')) -and ($how.Content -match [regex]::Escape('Major System Upgrade')) -and ($how.Content -match [regex]::Escape('$149')) -and ($how.Content -match [regex]::Escape('New System / Large Expansion')) -and ($how.Content -match [regex]::Escape('Price by Agreement')) -and ($how.Content -match [regex]::Escape('Upgrades are separate from maintenance.')) -and ($how.Content -match [regex]::Escape('You can buy an upgrade later whether you manage the system yourself or I manage it.'))
            $hasAboutAutomation = $about.Content -match [regex]::Escape("Automate the repetitive work that should not stay manual.")
            $hasAboutSubscriptionValue = $about.Content -match [regex]::Escape("One system can reduce the need for too many paid tools.")
            $hasNewTagline = $about.Content -match [regex]::Escape("Better systems for complex business needs.")
            $oldTaglineGone = -not ($about.Content -match [regex]::Escape("Simple systems for real estate businesses."))
            $hasAboutPortrait = ($about.Content -match [regex]::Escape('/static/images/about/key-castro.png')) -and ($about.Content -match [regex]::Escape('alt="Key Castro"'))
            $hasAboutProfessionalTitle = $about.Content -match [regex]::Escape("Custom Business App Developer &amp; Automation Specialist")
            $hasAboutProfileBlock = $about.Content -match [regex]::Escape('class="about-profile-block"')
            $hasAboutProfileName = $about.Content -match [regex]::Escape('class="about-profile-name">Key Castro</p>')
            $hasWhatIDo = $about.Content -match [regex]::Escape('<h1>What I do.</h1>')
            $approvedAboutDescription = "I build custom business systems and automation for real estate, property, and housing businesses. I help reduce manual work, organize scattered tasks and information, and create workflows that fit how the business really works. When useful, I also help reduce the need for too many separate tools and subscriptions by bringing key work into one system."
            $hasApprovedAboutDescription = $about.Content -match [regex]::Escape($approvedAboutDescription)
            $hasAboutValueRow = ($about.Content -match [regex]::Escape("Custom Systems")) -and ($about.Content -match [regex]::Escape("Built around your workflow")) -and ($about.Content -match [regex]::Escape("Automation")) -and ($about.Content -match [regex]::Escape("Less manual work")) -and ($about.Content -match [regex]::Escape("Real Results")) -and ($about.Content -match [regex]::Escape("More time for what matters"))
            $hasAboutStoryFlow = (($about.Content | Select-String -Pattern 'class="about-story-index"' -AllMatches).Matches.Count -eq 5) -and ($about.Content -match [regex]::Escape("THE PROBLEMS I HELP SOLVE")) -and ($about.Content -match [regex]::Escape("AUTOMATION")) -and ($about.Content -match [regex]::Escape("FEWER DISCONNECTED PLATFORMS")) -and ($about.Content -match [regex]::Escape("WHAT I BUILD")) -and ($about.Content -match [regex]::Escape("HOW I WORK"))
            $hasAboutPreservedDetails = ($about.Content -match [regex]::Escape("Missed follow-ups and deadlines")) -and ($about.Content -match [regex]::Escape("Software that does not fully fit")) -and ($about.Content -match [regex]::Escape("Recurring tasks and handoffs")) -and ($about.Content -match [regex]::Escape("The best option depends on the business.")) -and ($about.Content -match [regex]::Escape("Business-specific rules")) -and ($about.Content -match [regex]::Escape(">View Systems</a>"))
            $portraitLoads = ($portrait.StatusCode -eq 200) -and ($portrait.RawContentLength -gt 100000)
            $hasServicesPricingName = ($homePage.Content -match [regex]::Escape('>Services & Pricing</a>')) -and ($how.Content -match [regex]::Escape('<h1>Services & Pricing</h1>')) -and ($how.Content -match [regex]::Escape('<title>Services &amp; Pricing | Key Castro</title>'))
            $hasHomeFeaturedCtas = ($homePage.Content -match [regex]::Escape('class="home-featured-action-link home-featured-action-link--primary" href="/system-templates"')) -and ($homePage.Content -match [regex]::Escape('Explore All Systems')) -and ($homePage.Content -match [regex]::Escape('class="home-featured-action-link home-featured-action-link--secondary" href="/services"')) -and ($homePage.Content -match [regex]::Escape('See Services & Pricing'))
            $hasApprovedHomeCtaMicrocopy = ($homePage.Content -match [regex]::Escape('READY TO SEE MORE?')) -and ($homePage.Content -match [regex]::Escape('NEED DETAILS?')) -and ($homePage.Content -match [regex]::Escape('PLAN')) -and ($homePage.Content -match [regex]::Escape('BUILD')) -and ($homePage.Content -match [regex]::Escape('ORGANIZE')) -and ($homePage.Content -match [regex]::Escape('GROW'))
            $hasHomeCtaDesignCss = ($siteCss.Content -match [regex]::Escape('.home-featured-actions-section')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-action-link--primary')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-action-link--secondary')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-edge--left')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-edge--right'))
            $oldHomeCtaGone = -not ($homePage.Content -match [regex]::Escape('home-services-cta-link'))
            $oldHomeProcessGone = -not ($homePage.Content -match [regex]::Escape('How it works.')) -and -not ($homePage.Content -match [regex]::Escape('From your problem to a working system.')) -and -not ($homePage.Content -match [regex]::Escape('Tell me what you need.')) -and -not ($homePage.Content -match [regex]::Escape('Choose your system.')) -and -not ($homePage.Content -match [regex]::Escape('Choose who manages it.')) -and -not ($homePage.Content -match [regex]::Escape('class="home-process-list"'))
            if ($health.status -eq "ok" -and $health.version -eq $expectedVersion -and $hasServicesPricingName -and $hasHomeFeaturedCtas -and $hasApprovedHomeCtaMicrocopy -and $hasHomeCtaDesignCss -and $oldHomeCtaGone -and $oldHomeProcessGone -and $hasStudentHousing -and $hasThreeSystems -and $hasStep1 -and $hasStep2 -and $hasNoStep3 -and $oldBuildStepGone -and $hasManagementStep -and $hasViewSystemsButton -and $hasRequestSystemButton -and $finalCtaGone -and $hasExistingSystemPrice -and $hasThreeHomePriceCards -and $hasThreePricedSystemCards -and $hasPurchaseBoundary -and $hasExistingSystemContact -and $hasAgreementPrice -and $oldExistingQuoteGone -and $hasUsdOnlyPublicPricing -and $hasPricing -and $oldPricingGone -and $hasMaintenanceBoundary -and $hasUpgradePricing -and $hasAboutAutomation -and $hasAboutSubscriptionValue -and $hasNewTagline -and $oldTaglineGone -and $hasAboutPortrait -and $hasAboutProfessionalTitle -and $hasAboutProfileBlock -and $hasAboutProfileName -and $hasWhatIDo -and $hasApprovedAboutDescription -and $hasAboutValueRow -and $hasAboutStoryFlow -and $hasAboutPreservedDetails -and $portraitLoads) {
                $verified = $true
                break
            }
            $lastError = "Health/version/Home featured-systems CTA redesign/Services & Pricing/About/Systems content has not refreshed yet."
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
    Write-Host "About automation/problem update: confirmed LIVE"
    Write-Host "Approved About profile: confirmed LIVE"
    Write-Host "About lower story organization: confirmed LIVE"
    Write-Host "Home featured-systems CTA redesign: confirmed LIVE"
    Write-Host "Explore All Systems + Services & Pricing CTA destinations: confirmed LIVE"
    Write-Host "Old Home three-step process: confirmed removed"
    Write-Host "Pricing/service information: confirmed LIVE"
    Write-Host "Existing system `$160 pricing: confirmed LIVE"
    Write-Host "Price by Agreement wording: confirmed LIVE"
    Write-Host "Footer tagline: confirmed LIVE"
    Write-Host "Commit: $sha"
    Write-Host ""
}
finally {
    Pop-Location
}
