$ErrorActionPreference = "Stop"

$packageRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$documents = [Environment]::GetFolderPath("MyDocuments")
$target = Join-Path $documents "REALTY_SYSTEMS_FOUNDRY"
$legacyServiceId = "srv-dam749e1egvs738cppq0"
$desiredServiceName = "realtysystemsfoundry"
$legacyServiceName = "realtysystemsfoundry-legacy"
$liveBase = "https://realtysystemsfoundry.onrender.com"
$expectedVersion = "3.9.8"
$commitMessage = "Release 3.9.8 Render Hostname Migration - Resume and Git Preflight Cleanup"

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

function Get-RenderServiceRecords {
    param([Parameter(Mandatory=$true)][string]$RenderCommand)
    $raw = Get-NativeText -Command $RenderCommand -Arguments @("services", "-o", "json")
    if (-not $raw) { return @() }
    $parsed = $raw | ConvertFrom-Json
    $records = @()
    $candidates = @()
    if ($null -ne $parsed) {
        $topProperties = @($parsed.PSObject.Properties.Name)
        if ($topProperties -contains "services") {
            $candidates = @($parsed.services)
        } else {
            $candidates = @($parsed)
        }
    }
    foreach ($item in $candidates) {
        if ($null -eq $item) { continue }
        $propertyNames = @($item.PSObject.Properties.Name)
        if ($propertyNames -contains "service") {
            if ($null -ne $item.service) { $records += $item.service }
        } elseif (($propertyNames -contains "id") -and ($propertyNames -contains "name")) {
            $records += $item
        }
    }
    return @($records)
}

function Get-RenderApiKey {
    $candidate = [string]$env:RENDER_API_KEY
    if ($candidate -and $candidate.Trim()) {
        Write-Host "      Using RENDER_API_KEY from this CMD session." -ForegroundColor DarkGray
        return $candidate.Trim()
    }

    Write-Host ""
    Write-Host "Render needs an API key once so this migration can copy the CURRENT production environment variables securely." -ForegroundColor Yellow
    Write-Host "The key is used only in this PowerShell process. It is NOT written to the website, .env, Git, or the release ZIP." -ForegroundColor Gray
    Write-Host "If needed: Render Dashboard -> Account Settings -> API Keys -> Create API Key." -ForegroundColor Gray
    $secure = Read-Host "Paste your Render API key (input is hidden)" -AsSecureString
    if ($null -eq $secure -or $secure.Length -eq 0) {
        throw "A Render API key is required to copy production secrets safely. Nothing on Render was changed."
    }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if (-not $plain -or -not $plain.Trim()) {
        throw "The Render API key was empty. Nothing on Render was changed."
    }
    return $plain.Trim()
}

function Invoke-RenderApi {
    param(
        [Parameter(Mandatory=$true)][ValidateSet("GET","POST","PUT","PATCH","DELETE")][string]$Method,
        [Parameter(Mandatory=$true)][string]$Path,
        [Parameter(Mandatory=$true)][string]$ApiKey,
        $Body = $null
    )
    $uri = "https://api.render.com/v1$Path"
    $headers = @{
        Authorization = "Bearer $ApiKey"
        Accept = "application/json"
    }
    $params = @{
        Uri = $uri
        Method = $Method
        Headers = $headers
        TimeoutSec = 45
        ErrorAction = "Stop"
    }
    if ($null -ne $Body) {
        $params.ContentType = "application/json"
        $params.Body = ConvertTo-Json -InputObject $Body -Depth 12 -Compress
    }
    return Invoke-RestMethod @params
}

function Get-RenderDirectEnvVars {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceId,
        [Parameter(Mandatory=$true)][string]$ApiKey
    )
    $result = @()
    $cursor = $null
    do {
        $path = "/services/$ServiceId/env-vars?limit=100"
        if ($cursor) { $path += "&cursor=$([Uri]::EscapeDataString($cursor))" }
        $page = @(Invoke-RenderApi -Method GET -Path $path -ApiKey $ApiKey)
        $nextCursor = $null
        foreach ($item in $page) {
            if ($null -eq $item -or $null -eq $item.envVar) { continue }
            $result += [PSCustomObject]@{
                key = [string]$item.envVar.key
                value = [string]$item.envVar.value
            }
            if ($item.cursor) { $nextCursor = [string]$item.cursor }
        }
        if ($page.Count -lt 100 -or -not $nextCursor) { break }
        $cursor = $nextCursor
    } while ($true)
    return @($result)
}

function Get-RenderSecretFiles {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceId,
        [Parameter(Mandatory=$true)][string]$ApiKey
    )
    $result = @()
    $cursor = $null
    do {
        $path = "/services/$ServiceId/secret-files?limit=100"
        if ($cursor) { $path += "&cursor=$([Uri]::EscapeDataString($cursor))" }
        $page = @(Invoke-RenderApi -Method GET -Path $path -ApiKey $ApiKey)
        $nextCursor = $null
        foreach ($item in $page) {
            if ($null -eq $item -or $null -eq $item.secretFile) { continue }
            $result += [PSCustomObject]@{
                name = [string]$item.secretFile.name
                content = [string]$item.secretFile.content
            }
            if ($item.cursor) { $nextCursor = [string]$item.cursor }
        }
        if ($page.Count -lt 100 -or -not $nextCursor) { break }
        $cursor = $nextCursor
    } while ($true)
    return @($result)
}

function Get-LinkedRenderEnvironmentGroups {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceId,
        [Parameter(Mandatory=$true)][string]$ApiKey
    )
    $groups = @(Invoke-RenderApi -Method GET -Path "/env-groups?limit=100" -ApiKey $ApiKey)
    $linked = @()
    foreach ($group in $groups) {
        if ($null -eq $group -or -not $group.id) { continue }
        $isLinked = $false
        foreach ($link in @($group.serviceLinks)) {
            if ($null -ne $link -and [string]$link.id -eq $ServiceId) { $isLinked = $true; break }
        }
        if ($isLinked) {
            $full = Invoke-RenderApi -Method GET -Path "/env-groups/$([string]$group.id)" -ApiKey $ApiKey
            if ($null -ne $full) { $linked += $full }
        }
    }
    return @($linked)
}

function Ensure-EnvironmentGroupsLinked {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceId,
        $SourceGroups = @(),
        [Parameter(Mandatory=$true)][string]$ApiKey
    )
    $SourceGroups = @($SourceGroups)
    if ($SourceGroups.Count -eq 0) { return }
    $currentGroups = @(Invoke-RenderApi -Method GET -Path "/env-groups?limit=100" -ApiKey $ApiKey)
    foreach ($sourceGroup in $SourceGroups) {
        $groupId = [string]$sourceGroup.id
        if (-not $groupId) { continue }
        $alreadyLinked = $false
        $meta = @($currentGroups | Where-Object { [string]$_.id -eq $groupId } | Select-Object -First 1)
        if ($meta.Count -gt 0) {
            foreach ($link in @($meta[0].serviceLinks)) {
                if ($null -ne $link -and [string]$link.id -eq $ServiceId) { $alreadyLinked = $true; break }
            }
        }
        if (-not $alreadyLinked) {
            Invoke-RenderApi -Method POST -Path "/env-groups/$groupId/services/$ServiceId" -ApiKey $ApiKey | Out-Null
        }
    }
    Write-Host "      Linked environment groups preserved: $($SourceGroups.Count)." -ForegroundColor DarkGray
}

function Test-ValidRenderEnvKey {
    param([string]$Key)
    if ($null -eq $Key) { return $false }
    $candidate = $Key.Trim()
    if (-not $candidate) { return $false }
    if ($candidate -eq ".") { return $false }
    # Render allows letters, digits, underscore, hyphen, and period, but the
    # key cannot start with a digit and cannot be a single period. We use a
    # stricter conventional start (letter/underscore) so malformed legacy keys
    # can never block the replacement service.
    return [bool]($candidate -match '^[A-Za-z_][A-Za-z0-9_.-]*$')
}

function Get-SanitizedRenderEnvVars {
    param(
        $Items = @(),
        [string[]]$RequiredKeys = @()
    )
    $inputItems = @()
    if ($null -ne $Items) { $inputItems = @($Items) }
    $clean = New-Object System.Collections.ArrayList
    $skipped = 0
    foreach ($item in $inputItems) {
        if ($null -eq $item) { continue }
        $key = [string]$item.key
        if (-not (Test-ValidRenderEnvKey -Key $key)) {
            $skipped++
            continue
        }
        Set-EnvVarValue -Items $clean -Key $key.Trim() -Value ([string]$item.value)
    }
    if ($skipped -gt 0) {
        Write-Host "      Skipped $skipped malformed legacy environment-variable key(s) before contacting Render." -ForegroundColor DarkGray
    }
    foreach ($required in @($RequiredKeys)) {
        $found = $false
        foreach ($item in @($clean)) {
            if ([string]$item.key -eq $required -and ([string]$item.value).Trim()) { $found = $true; break }
        }
        if (-not $found) {
            throw "Required production environment variable is missing after key validation: $required"
        }
    }
    return @($clean)
}

function Set-EnvVarValue {
    param(
        [System.Collections.ArrayList]$Items,
        [Parameter(Mandatory=$true)][string]$Key,
        [Parameter(Mandatory=$true)][string]$Value
    )
    if ($null -eq $Items) { throw "Internal migration error: environment-variable collection was null." }
    for ($i = 0; $i -lt $Items.Count; $i++) {
        if ([string]$Items[$i].key -eq $Key) {
            $Items[$i] = [PSCustomObject]@{ key = $Key; value = $Value }
            return
        }
    }
    [void]$Items.Add([PSCustomObject]@{ key = $Key; value = $Value })
}

function Get-EffectiveEnvMap {
    param(
        $EnvVars = @(),
        $EnvGroups = @()
    )
    $EnvVars = @($EnvVars)
    $EnvGroups = @($EnvGroups)
    $map = @{}
    $orderedGroups = @($EnvGroups | Sort-Object { try { [DateTimeOffset]::Parse([string]$_.createdAt) } catch { [DateTimeOffset]::MinValue } })
    foreach ($group in $orderedGroups) {
        foreach ($item in @($group.envVars)) {
            if ($null -eq $item) { continue }
            if ($item.envVar) {
                if ($item.envVar.key) { $map[[string]$item.envVar.key] = [string]$item.envVar.value }
            } elseif ($item.key) {
                $map[[string]$item.key] = [string]$item.value
            }
        }
    }
    foreach ($item in $EnvVars) {
        if ($null -ne $item -and $item.key) { $map[[string]$item.key] = [string]$item.value }
    }
    return $map
}

function New-StrongSecret {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes)
}

function Get-LocalOwnerToken {
    param([Parameter(Mandatory=$true)][string]$TargetFolder)
    $path = Join-Path $TargetFolder ".owner_inbox.json"
    if (!(Test-Path $path)) {
        throw "Private RSF INBOX config is missing. The migration needs its existing token so the private inbox keeps working."
    }
    $cfg = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    $token = [string]$cfg.token
    if (-not $token -or -not $token.Trim()) {
        throw "Private RSF INBOX config exists but its token is empty."
    }
    return $token.Trim()
}

function Get-ProjectContactEmail {
    param([Parameter(Mandatory=$true)][string]$TargetFolder)
    $statePath = Join-Path $TargetFolder "PROJECT_STATE.json"
    if (!(Test-Path $statePath)) { throw "PROJECT_STATE.json is missing." }
    $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
    $email = [string]$state.public_contact_email
    if (-not $email -or -not $email.Trim()) {
        throw "The project state does not contain a public contact email."
    }
    return $email.Trim()
}

function Get-RenderPostgresRecords {
    param([Parameter(Mandatory=$true)][string]$ApiKey)
    $result = @()
    $cursor = $null
    do {
        $path = "/postgres?limit=100&includeReplicas=false"
        if ($cursor) { $path += "&cursor=$([Uri]::EscapeDataString($cursor))" }
        $page = @(Invoke-RenderApi -Method GET -Path $path -ApiKey $ApiKey)
        $nextCursor = $null
        foreach ($item in $page) {
            if ($null -eq $item) { continue }
            $candidate = $null
            if ($item.postgres) { $candidate = $item.postgres }
            elseif ($item.id) { $candidate = $item }
            if ($null -ne $candidate -and $candidate.id) { $result += $candidate }
            if ($item.cursor) { $nextCursor = [string]$item.cursor }
        }
        if ($page.Count -lt 100 -or -not $nextCursor) { break }
        $cursor = $nextCursor
    } while ($true)
    return @($result)
}

function Resolve-RenderDatabaseUrl {
    param([Parameter(Mandatory=$true)][string]$ApiKey)
    $databases = @(Get-RenderPostgresRecords -ApiKey $ApiKey)
    if ($databases.Count -eq 0) {
        throw "No Render Postgres instance is available in this account, so DATABASE_URL cannot be rebuilt safely."
    }

    $selected = $null
    if ($databases.Count -eq 1) {
        $selected = $databases[0]
        Write-Host "      Found one Render Postgres database; using it for the existing inquiry inbox." -ForegroundColor DarkGray
    } else {
        Write-Host ""
        Write-Host "More than one Render Postgres database exists. Choose the database used by this website's inquiry inbox:" -ForegroundColor Yellow
        for ($i = 0; $i -lt $databases.Count; $i++) {
            $name = [string]$databases[$i].name
            $id = [string]$databases[$i].id
            $region = [string]$databases[$i].region
            Write-Host "  [$($i + 1)] $name  $id  $region"
        }
        $choice = Read-Host "Enter the number"
        $number = 0
        if (-not [int]::TryParse($choice, [ref]$number) -or $number -lt 1 -or $number -gt $databases.Count) {
            throw "Invalid Postgres selection. Nothing on Render was changed."
        }
        $selected = $databases[$number - 1]
    }

    $dbId = [string]$selected.id
    $info = Invoke-RenderApi -Method GET -Path "/postgres/$dbId/connection-info" -ApiKey $ApiKey
    $url = [string]$info.internalConnectionString
    if (-not $url -or -not $url.Trim()) {
        $url = [string]$info.internal_connection_string
    }
    if (-not $url -or -not $url.Trim()) {
        throw "Render returned the database record but did not provide an internal connection string."
    }
    Write-Host "      Existing Render Postgres connection resolved securely. The URL/password were not printed." -ForegroundColor DarkGray
    return $url.Trim()
}

function Resolve-ProductionEnvVars {
    param(
        $SourceEnvVars = @(),
        $SourceEnvGroups = @(),
        [Parameter(Mandatory=$true)][string]$TargetFolder,
        [Parameter(Mandatory=$true)][string]$ApiKey,
        [Parameter(Mandatory=$true)][string]$LiveBase
    )
    $SourceEnvVars = @($SourceEnvVars)
    $SourceEnvGroups = @($SourceEnvGroups)
    $rawMap = Get-EffectiveEnvMap -EnvVars $SourceEnvVars -EnvGroups $SourceEnvGroups
    $map = @{}
    $invalidSourceKeyCount = 0
    foreach ($rawKey in @($rawMap.Keys)) {
        $keyText = [string]$rawKey
        if (Test-ValidRenderEnvKey -Key $keyText) {
            $map[$keyText.Trim()] = [string]$rawMap[$rawKey]
        } else {
            $invalidSourceKeyCount++
        }
    }
    if ($invalidSourceKeyCount -gt 0) {
        Write-Host "      Ignored $invalidSourceKeyCount malformed legacy environment-variable key(s)." -ForegroundColor DarkGray
    }
    $localToken = Get-LocalOwnerToken -TargetFolder $TargetFolder
    $contactEmail = Get-ProjectContactEmail -TargetFolder $TargetFolder

    if ($map.ContainsKey("OWNER_INBOX_TOKEN") -and ([string]$map["OWNER_INBOX_TOKEN"]).Trim()) {
        if ([string]$map["OWNER_INBOX_TOKEN"] -ne $localToken) {
            throw "Safety stop: the old Render OWNER_INBOX_TOKEN does not match the locally preserved RSF INBOX token."
        }
    } else {
        $map["OWNER_INBOX_TOKEN"] = $localToken
        Write-Host "      OWNER_INBOX_TOKEN recovered from the private local RSF INBOX config." -ForegroundColor DarkGray
    }

    if (-not $map.ContainsKey("SECRET_KEY") -or -not ([string]$map["SECRET_KEY"]).Trim()) {
        $map["SECRET_KEY"] = New-StrongSecret
        Write-Host "      Generated a new strong production SECRET_KEY for the replacement service." -ForegroundColor DarkGray
    }
    if (-not $map.ContainsKey("CONTACT_EMAIL") -or -not ([string]$map["CONTACT_EMAIL"]).Trim()) {
        $map["CONTACT_EMAIL"] = $contactEmail
        Write-Host "      CONTACT_EMAIL restored from the approved project contact email." -ForegroundColor DarkGray
    }
    if (-not $map.ContainsKey("DATABASE_URL") -or -not ([string]$map["DATABASE_URL"]).Trim()) {
        $map["DATABASE_URL"] = Resolve-RenderDatabaseUrl -ApiKey $ApiKey
    }

    $map["APP_ENV"] = "production"
    $map["PUBLIC_BASE_URL"] = $LiveBase
    $map["TRUSTED_HOSTS"] = "realtysystemsfoundry.onrender.com,.onrender.com"
    $map["CONTACT_DELIVERY_MODE"] = "database"
    if (-not $map.ContainsKey("OWNER_TIMEZONE") -or -not ([string]$map["OWNER_TIMEZONE"]).Trim()) {
        $map["OWNER_TIMEZONE"] = "Asia/Manila"
    }

    $required = @("SECRET_KEY", "CONTACT_EMAIL", "DATABASE_URL", "OWNER_INBOX_TOKEN", "PUBLIC_BASE_URL", "TRUSTED_HOSTS")
    foreach ($key in $required) {
        if (-not $map.ContainsKey($key) -or -not ([string]$map[$key]).Trim()) {
            throw "Required production setting could not be resolved safely: $key"
        }
    }

    # Every inherited key was already validated above and every required key is
    # explicitly validated here. Build the final array directly so Windows
    # PowerShell 5.1 never has to bind an empty intermediate collection.
    $items = New-Object System.Collections.ArrayList
    foreach ($key in @($map.Keys)) {
        if (-not (Test-ValidRenderEnvKey -Key ([string]$key))) { continue }
        [void]$items.Add([PSCustomObject]@{ key = [string]$key; value = [string]$map[$key] })
    }
    if ($items.Count -eq 0) {
        throw "Production environment resolution unexpectedly produced zero variables. Nothing on Render was changed."
    }
    return @($items)
}

function Assert-SourceProductionConfiguration {
    param(
        $EnvVars = @(),
        $EnvGroups = @(),
        [Parameter(Mandatory=$true)][string]$TargetFolder
    )
    $EnvVars = @($EnvVars)
    $EnvGroups = @($EnvGroups)
    # Recreate Render's effective-value rule only for validation: linked groups
    # first, direct service variables last. Service-level values always win.
    $map = @{}
    $orderedGroups = @($EnvGroups | Sort-Object { try { [DateTimeOffset]::Parse([string]$_.createdAt) } catch { [DateTimeOffset]::MinValue } })
    foreach ($group in $orderedGroups) {
        foreach ($item in @($group.envVars)) {
            if ($null -ne $item -and $item.key) { $map[[string]$item.key] = [string]$item.value }
        }
    }
    foreach ($item in $EnvVars) {
        $map[[string]$item.key] = [string]$item.value
    }
    $required = @("SECRET_KEY", "CONTACT_EMAIL", "DATABASE_URL", "OWNER_INBOX_TOKEN")
    $missing = @()
    foreach ($key in $required) {
        if (-not $map.ContainsKey($key) -or -not ([string]$map[$key]).Trim()) { $missing += $key }
    }
    if ($missing.Count -gt 0) {
        throw "The original Render production configuration is missing required values: $($missing -join ', '). Migration stopped BEFORE renaming or creating any service."
    }

    $ownerConfigPath = Join-Path $TargetFolder ".owner_inbox.json"
    if (Test-Path $ownerConfigPath) {
        $ownerConfig = Get-Content -LiteralPath $ownerConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $localToken = [string]$ownerConfig.token
        if ($localToken -and ($localToken -ne [string]$map["OWNER_INBOX_TOKEN"])) {
            throw "Safety stop: the local RSF INBOX token does not match the effective production OWNER_INBOX_TOKEN. Nothing on Render was changed."
        }
    }
}

function Copy-ProductionConfigurationToService {
    param(
        [Parameter(Mandatory=$true)][string]$ServiceId,
        $SourceEnvVars = @(),
        $SourceSecretFiles = @(),
        [Parameter(Mandatory=$true)][string]$ApiKey,
        [Parameter(Mandatory=$true)][string]$LiveBase
    )
    $SourceEnvVars = @($SourceEnvVars)
    $SourceSecretFiles = @($SourceSecretFiles)
    $copy = New-Object System.Collections.ArrayList
    foreach ($item in $SourceEnvVars) {
        [void]$copy.Add([PSCustomObject]@{ key = [string]$item.key; value = [string]$item.value })
    }
    Set-EnvVarValue -Items $copy -Key "APP_ENV" -Value "production"
    Set-EnvVarValue -Items $copy -Key "PUBLIC_BASE_URL" -Value $LiveBase
    Set-EnvVarValue -Items $copy -Key "TRUSTED_HOSTS" -Value "realtysystemsfoundry.onrender.com,.onrender.com"

    $hasDeliveryMode = $false
    $hasTimezone = $false
    foreach ($item in $copy) {
        if ([string]$item.key -eq "CONTACT_DELIVERY_MODE") { $hasDeliveryMode = $true }
        if ([string]$item.key -eq "OWNER_TIMEZONE") { $hasTimezone = $true }
    }
    if (-not $hasDeliveryMode) { Set-EnvVarValue -Items $copy -Key "CONTACT_DELIVERY_MODE" -Value "database" }
    if (-not $hasTimezone) { Set-EnvVarValue -Items $copy -Key "OWNER_TIMEZONE" -Value "Asia/Manila" }

    $requiredForDeploy = @("SECRET_KEY", "CONTACT_EMAIL", "DATABASE_URL", "OWNER_INBOX_TOKEN", "PUBLIC_BASE_URL", "TRUSTED_HOSTS")
    $envBody = @(Get-SanitizedRenderEnvVars -Items @($copy) -RequiredKeys $requiredForDeploy)
    Write-Host "      Environment-variable key preflight passed: $($envBody.Count) valid key(s)." -ForegroundColor DarkGray
    Invoke-RenderApi -Method PUT -Path "/services/$ServiceId/env-vars" -ApiKey $ApiKey -Body $envBody | Out-Null

    if ($SourceSecretFiles.Count -gt 0) {
        $secretBody = @($SourceSecretFiles | ForEach-Object { [PSCustomObject]@{ name = [string]$_.name; content = [string]$_.content } })
        Invoke-RenderApi -Method PUT -Path "/services/$ServiceId/secret-files" -ApiKey $ApiKey -Body $secretBody | Out-Null
    }
    Write-Host "      Production configuration copied securely: $($envBody.Count) environment variables and $($SourceSecretFiles.Count) secret file(s). Values were not printed or written to disk." -ForegroundColor DarkGray
}

function Write-RenderDeployDiagnostics {
    param(
        [Parameter(Mandatory=$true)][string]$RenderCommand,
        [Parameter(Mandatory=$true)][string]$ServiceId
    )
    Write-Host ""
    Write-Host "      Render deployment failed. Showing non-secret deployment diagnostics before rollback:" -ForegroundColor Yellow
    try { & $RenderCommand deploys list $ServiceId -o text 2>&1 | Select-Object -Last 40 | ForEach-Object { Write-Host $_ } } catch {}
    try { & $RenderCommand logs -r $ServiceId --type build --limit 80 -o text 2>&1 | ForEach-Object { Write-Host $_ } } catch {}
    try { & $RenderCommand logs -r $ServiceId --level error --limit 80 -o text 2>&1 | ForEach-Object { Write-Host $_ } } catch {}
    Write-Host ""
}

function Wait-ForBasicService {
    param(
        [Parameter(Mandatory=$true)][string]$BaseUrl,
        [int]$Attempts = 18
    )
    $last = ""
    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {
        try {
            $stamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
            $health = Invoke-RestMethod -Uri "$BaseUrl/system/health?bootstrap=$stamp" -Method Get -TimeoutSec 30
            if ($health.status -eq "ok") { return $true }
            $last = "Health endpoint returned an unexpected response."
        } catch {
            $last = $_.Exception.Message
        }
        if ($attempt -lt $Attempts) {
            Write-Host "      New hostname bootstrap attempt $attempt/$Attempts not ready yet; retrying..." -ForegroundColor DarkGray
            Start-Sleep -Seconds 10
        }
    }
    throw "The requested Render hostname did not become reachable. Last result: $last"
}

function Test-PrivateInboxOnHost {
    param(
        [Parameter(Mandatory=$true)][string]$BaseUrl,
        [Parameter(Mandatory=$true)][string]$TargetFolder
    )
    $ownerConfigPath = Join-Path $TargetFolder ".owner_inbox.json"
    if (!(Test-Path $ownerConfigPath)) {
        Write-Host "      No local private inbox config found; skipping token/database continuity check." -ForegroundColor DarkGray
        return
    }
    $ownerConfig = Get-Content -LiteralPath $ownerConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $token = [string]$ownerConfig.token
    if (-not $token) {
        throw "Private inbox config exists but does not contain a token. Migration stopped before switching endpoints."
    }
    $headers = @{ Authorization = "Bearer $token" }
    try {
        $ownerHealth = Invoke-RestMethod -Uri "$BaseUrl/__owner_api/health" -Headers $headers -Method Get -TimeoutSec 30
    } catch {
        throw "New Render service is public, but the private RSF Inbox token/database check failed. The legacy service is being kept as rollback. Error: $($_.Exception.Message)"
    }
    if ($ownerHealth.status -ne "ok") {
        throw "New Render service did not pass the private RSF Inbox continuity check. The legacy service is being kept as rollback."
    }
    Write-Host "      Private RSF Inbox token + database continuity confirmed on the new service." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  REALTY SYSTEMS FOUNDRY - UPDATE + AUTOMATIC LIVE DEPLOY" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "This single run will:" -ForegroundColor Gray
Write-Host "  1. update the local website and preserve private configuration"
Write-Host "  2. run the full automated test suite"
Write-Host "  3. check Git and Render tooling"
Write-Host "  4. securely reconstruct the required production settings from trusted local + Render sources"
Write-Host "  5. clone the service, apply the reconstructed production configuration, and create realtysystemsfoundry.onrender.com"
Write-Host "  6. verify the new host and private RSF Inbox/database continuity"
Write-Host "  7. commit and push approved website files plus the new active service ID"
Write-Host "  8. deploy the exact release commit to the new Render service"
Write-Host "  9. verify https://realtysystemsfoundry.onrender.com and switch the local inbox endpoint"
Write-Host ""

Write-Host "[A/9] Applying the website update and running local tests..." -ForegroundColor Yellow
$installer = Join-Path $packageRoot "scripts\INSTALL_WEBSITE.ps1"
if (!(Test-Path $installer)) { throw "Installer not found: $installer" }
& $installer -SkipLaunch

if (!(Test-Path $target)) { throw "Installed website folder was not found: $target" }
if (!(Test-Path (Join-Path $target ".git"))) {
    throw "The installed website is not connected to its existing Git repository. Automatic deployment stopped safely."
}

Push-Location $target
try {
    Write-Host "[B/9] Checking Git repository and deployment remotes..." -ForegroundColor Yellow
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
        "REALTY_SYSTEMS_FOUNDRY_LAUNCHER.ps1", "REALTY_SYSTEMS_FOUNDRY_INBOX_LAUNCHER.ps1", "REALTY_SYSTEMS_FOUNDRY.ico",
        "START_REALTY_SYSTEMS_FOUNDRY.bat", "SETUP_REALTY_SYSTEMS_FOUNDRY.bat", "STOP_REALTY_SYSTEMS_FOUNDRY.bat",
        "KEY_CASTRO_LAUNCHER.ps1", "KEY_CASTRO_INBOX_LAUNCHER.ps1", "KEY_CASTRO.ico",
        "START_KEY_CASTRO_WEBSITE.bat", "SETUP_KEY_CASTRO_WEBSITE.bat", "STOP_KEY_CASTRO_WEBSITE.bat",
        "APPLY_UPDATE_AND_DEPLOY_LIVE.bat",
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

    Write-Host "[C/9] Creating the exact Render hostname with secure production configuration copy..." -ForegroundColor Yellow
    $render = Get-Command render.exe -ErrorAction SilentlyContinue
    if (!$render) { $render = Get-Command render -ErrorAction SilentlyContinue }
    if (!$render) {
        throw "Render CLI was not found. Nothing was migrated or deployed. Restore the Render CLI and rerun this updater."
    }

    # Resume safely if the replacement service already exists and is healthy.
    # This avoids asking for the API key again after a previous run completed the
    # Render migration but stopped later during Git preflight.
    $records = Get-RenderServiceRecords -RenderCommand $render.Source
    $active = @($records | Where-Object { ([string]$_.name -eq $desiredServiceName) -and ([string]$_.id -ne $legacyServiceId) } | Select-Object -First 1)
    $activeServiceId = $null
    $resumeHealthy = $false
    if ($active.Count -gt 0) {
        $activeServiceId = [string]$active[0].id
        Write-Host "      Existing replacement Render service detected: $activeServiceId" -ForegroundColor DarkGray
        try {
            Wait-ForBasicService -BaseUrl $liveBase -Attempts 3 | Out-Null
            Test-PrivateInboxOnHost -BaseUrl $liveBase -TargetFolder $target
            $resumeHealthy = $true
            Write-Host "      Existing replacement is healthy; resuming after the previous Git preflight stop. No API key is needed for this resume." -ForegroundColor DarkGray
        } catch {
            Write-Host "      Existing replacement needs configuration recovery; continuing with the secure Render API migration path." -ForegroundColor DarkGray
        }
    }

    if (-not $resumeHealthy) {
        # Render CLI cloning currently does not copy direct service environment variables.
        # Read them from the original service with Render's official API BEFORE making
        # any service-name change, then copy them to the replacement service in memory.
        $apiKeyWasAlreadySet = [bool]([string]$env:RENDER_API_KEY)
        $originalApiKeyEnv = [string]$env:RENDER_API_KEY
        $renderApiKey = Get-RenderApiKey
        $env:RENDER_API_KEY = $renderApiKey
        try {
            Write-Host "      Reading any reusable configuration from the original Render service..." -ForegroundColor DarkGray
            $sourceEnvVars = @(Get-RenderDirectEnvVars -ServiceId $legacyServiceId -ApiKey $renderApiKey)
            $sourceSecretFiles = @(Get-RenderSecretFiles -ServiceId $legacyServiceId -ApiKey $renderApiKey | Where-Object { $_.name -and $_.content })
            $sourceEnvGroups = @(Get-LinkedRenderEnvironmentGroups -ServiceId $legacyServiceId -ApiKey $renderApiKey)
            $resolvedEnvVars = @(Resolve-ProductionEnvVars -SourceEnvVars $sourceEnvVars -SourceEnvGroups $sourceEnvGroups -TargetFolder $target -ApiKey $renderApiKey -LiveBase $liveBase)
            Write-Host "      Production configuration resolved safely. Secret values will never be printed or written to the release." -ForegroundColor DarkGray

            $records = Get-RenderServiceRecords -RenderCommand $render.Source
            $legacy = @($records | Where-Object { [string]$_.id -eq $legacyServiceId } | Select-Object -First 1)
            $active = @($records | Where-Object { ([string]$_.name -eq $desiredServiceName) -and ([string]$_.id -ne $legacyServiceId) } | Select-Object -First 1)
            $createdNow = $false
            $legacyRenamedNow = $false

            if ($active.Count -eq 0) {
            if ($legacy.Count -eq 0) {
                throw "Could not find the original Render service ID $legacyServiceId. Migration stopped safely."
            }

            $legacyNameNow = [string]$legacy[0].name
            if ($legacyNameNow -ne $legacyServiceName) {
                Write-Host "      Renaming the original service to $legacyServiceName so the exact company name can be used by the replacement service..." -ForegroundColor DarkGray
                Invoke-Native -Command $render.Source -Arguments @("services", "update", $legacyServiceId, "--name", $legacyServiceName, "--confirm", "-o", "text")
                $legacyRenamedNow = $true
            }

            try {
                Write-Host "      Cloning the existing Render service configuration into '$desiredServiceName'..." -ForegroundColor DarkGray
                Invoke-Native -Command $render.Source -Arguments @("services", "create", "--from", $legacyServiceId, "--name", $desiredServiceName, "--confirm", "-o", "text")
                $createdNow = $true
            } catch {
                if ($legacyRenamedNow) {
                    try { Invoke-Native -Command $render.Source -Arguments @("services", "update", $legacyServiceId, "--name", $desiredServiceName, "--confirm", "-o", "text") } catch {}
                }
                throw "Render could not create the replacement service. The original service was kept. Error: $($_.Exception.Message)"
            }

            Start-Sleep -Seconds 3
            $records = Get-RenderServiceRecords -RenderCommand $render.Source
            $active = @($records | Where-Object { ([string]$_.name -eq $desiredServiceName) -and ([string]$_.id -ne $legacyServiceId) } | Select-Object -First 1)
            if ($active.Count -eq 0) {
                if ($legacyRenamedNow) {
                    try { Invoke-Native -Command $render.Source -Arguments @("services", "update", $legacyServiceId, "--name", $desiredServiceName, "--confirm", "-o", "text") } catch {}
                }
                throw "Render created a clone but its replacement service ID could not be resolved. Migration stopped before Git changes."
            }
        } else {
            Write-Host "      Replacement Render service already exists; continuing the interrupted migration safely." -ForegroundColor DarkGray
        }

        $activeServiceId = [string]$active[0].id
        if (-not $activeServiceId) { throw "Replacement Render service ID could not be resolved." }
        Write-Host "      New active Render service ID: $activeServiceId" -ForegroundColor DarkGray

        try {
            Write-Host "      Restoring production environment variables/secrets to the replacement service BEFORE its verified deploy..." -ForegroundColor DarkGray
            Copy-ProductionConfigurationToService -ServiceId $activeServiceId -SourceEnvVars $resolvedEnvVars -SourceSecretFiles $sourceSecretFiles -ApiKey $renderApiKey -LiveBase $liveBase
            Ensure-EnvironmentGroupsLinked -ServiceId $activeServiceId -SourceGroups $sourceEnvGroups -ApiKey $renderApiKey

            # The clone command can start an initial deploy without env vars. That deploy may
            # fail; the deploy below is the authoritative post-configuration deployment.
            Invoke-Native -Command $render.Source -Arguments @("deploys", "create", $activeServiceId, "--wait", "--confirm", "-o", "text")
            Wait-ForBasicService -BaseUrl $liveBase -Attempts 18 | Out-Null
            Test-PrivateInboxOnHost -BaseUrl $liveBase -TargetFolder $target
        } catch {
            Write-RenderDeployDiagnostics -RenderCommand $render.Source -ServiceId $activeServiceId
            if ($createdNow) {
                Write-Host "      Replacement did not pass migration checks. Deleting only the new service and restoring the original service name..." -ForegroundColor DarkGray
                try { Invoke-Native -Command $render.Source -Arguments @("services", "delete", $activeServiceId, "--confirm", "-o", "text") } catch {}
                try { Invoke-Native -Command $render.Source -Arguments @("services", "update", $legacyServiceId, "--name", $desiredServiceName, "--confirm", "-o", "text") } catch {}
            }
            throw
        }
        }
        finally {
            $renderApiKey = $null
            if ($apiKeyWasAlreadySet) {
                $env:RENDER_API_KEY = $originalApiKeyEnv
            } else {
                Remove-Item Env:RENDER_API_KEY -ErrorAction SilentlyContinue
            }
        }
    }

    if (-not $activeServiceId) {
        throw "Replacement Render service ID could not be resolved before Git staging."
    }

    # Record the replacement service ID in source-controlled project state. The
    # original service remains online under the legacy service name as rollback.
    $statePath = Join-Path $target "PROJECT_STATE.json"
    try {
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $state.version = $expectedVersion
        $state.current_version = $expectedVersion
        $state.official_live_url = $liveBase
        $state.render.service_name = $desiredServiceName
        $state.render.service_id = $activeServiceId
        $state.render.migration_note = "v3.9.8 resumed the already healthy replacement Render service after the prior Git whitespace preflight stop, then completed clean source control, exact deploy, live verification, and private RSF Inbox/database continuity checks. The original service remains as rollback."
        if (-not ($state.render.PSObject.Properties.Name -contains "legacy_service_id")) {
            $state.render | Add-Member -NotePropertyName legacy_service_id -NotePropertyValue $legacyServiceId
        } else {
            $state.render.legacy_service_id = $legacyServiceId
        }
        if (-not ($state.render.PSObject.Properties.Name -contains "legacy_service_name")) {
            $state.render | Add-Member -NotePropertyName legacy_service_name -NotePropertyValue $legacyServiceName
        } else {
            $state.render.legacy_service_name = $legacyServiceName
        }
        $state | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $statePath -Encoding UTF8
    } catch {
        throw "The new Render service is healthy, but PROJECT_STATE.json could not be updated with its service ID: $($_.Exception.Message)"
    }

    Write-Host "[D/9] Staging only approved website release files..." -ForegroundColor Yellow
    $approvedPaths = @(
        "app", "scripts", "tests", "docs",
        ".env.example", ".gitignore", "config.py", "run.py", "wsgi.py",
        "requirements.txt", "requirements-production.txt",
        "README.md", "CHANGELOG.md", "DELIVERY_REPORT.md", "RELEASE_AUDIT.md",
        "VERSION.txt", "PROJECT_STATE.json", "DEVELOPER_HANDOFF.md",
        "NEXT_DEVELOPER_READ_THIS_FIRST.md", "SECURITY_AND_SHARING_NOTES.md",
        "00_FUTURE_DEVELOPER_READ_THIS_PLAN.md",
        "REALTY_SYSTEMS_FOUNDRY_LAUNCHER.ps1", "REALTY_SYSTEMS_FOUNDRY_INBOX_LAUNCHER.ps1", "REALTY_SYSTEMS_FOUNDRY.ico",
        "START_REALTY_SYSTEMS_FOUNDRY.bat", "SETUP_REALTY_SYSTEMS_FOUNDRY.bat", "STOP_REALTY_SYSTEMS_FOUNDRY.bat",
        "KEY_CASTRO_LAUNCHER.ps1", "KEY_CASTRO_INBOX_LAUNCHER.ps1", "KEY_CASTRO.ico",
        "START_KEY_CASTRO_WEBSITE.bat", "SETUP_KEY_CASTRO_WEBSITE.bat", "STOP_KEY_CASTRO_WEBSITE.bat",
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

    Write-Host "[E/9] Creating the release commit when needed..." -ForegroundColor Yellow
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

    Write-Host "[F/9] Pushing GitHub repositories..." -ForegroundColor Yellow
    Invoke-Native -Command $git.Source -Arguments @("push", "origin", "main")
    Invoke-Native -Command $git.Source -Arguments @("push", "renderdeploy", "main")

    Write-Host "[G/9] Triggering Render deployment..." -ForegroundColor Yellow
    Invoke-Native -Command $render.Source -Arguments @("deploys", "create", $activeServiceId, "--commit", $sha, "--wait", "--confirm", "-o", "text")

    Write-Host "[H/9] Verifying the LIVE website..." -ForegroundColor Yellow
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
            $hasExistingSystemPrice = ($homePage.Content -match [regex]::Escape('$199')) -and ($systems.Content -match [regex]::Escape('$199')) -and ($detail.Content -match [regex]::Escape('$199')) -and ($how.Content -match [regex]::Escape('$199'))
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
            $hasMaintenanceBoundary = ($how.Content -match [regex]::Escape('Management is optional.')) -and ($how.Content -match [regex]::Escape('$0/month')) -and ($how.Content -match [regex]::Escape('No management fee')) -and ($how.Content -match [regex]::Escape('Optional managed care. Same service; choose monthly or yearly billing.')) -and ($how.Content -match [regex]::Escape('What we manage')) -and ($how.Content -match [regex]::Escape('We handle:')) -and ($how.Content -match [regex]::Escape('Hosting and deployment')) -and ($how.Content -match [regex]::Escape('Technical fixes for the current system')) -and ($how.Content -match [regex]::Escape('Managed care does not include:')) -and ($how.Content -match [regex]::Escape('New features')) -and ($how.Content -match [regex]::Escape('Workflow changes')) -and ($how.Content -match [regex]::Escape('Connections to other tools'))
            $hasUpgradePricing = ($how.Content -match [regex]::Escape('Minor System Upgrade')) -and ($how.Content -match [regex]::Escape('$79')) -and ($how.Content -match [regex]::Escape('Major System Upgrade')) -and ($how.Content -match [regex]::Escape('$149')) -and ($how.Content -match [regex]::Escape('New System / Large Expansion')) -and ($how.Content -match [regex]::Escape('Price by Agreement')) -and ($how.Content -match [regex]::Escape('Upgrades are separate from maintenance.')) -and ($how.Content -match [regex]::Escape('You can buy an upgrade later whether you manage the system yourself or we manage it.'))
            $hasAboutAutomation = $about.Content -match [regex]::Escape("Automate the repetitive work that should not stay manual.")
            $hasAboutSubscriptionValue = $about.Content -match [regex]::Escape("One system can reduce the need for too many paid tools.")
            $hasNewTagline = $about.Content -match [regex]::Escape("Technology built for real estate operations.")
            $oldTaglineGone = -not ($about.Content -match [regex]::Escape("Simple systems for real estate businesses."))
            $hasAboutPortrait = ($about.Content -match [regex]::Escape('/static/images/about/key-castro.png')) -and ($about.Content -match [regex]::Escape('alt="Key Castro"'))
            $hasAboutProfessionalTitle = $about.Content -match [regex]::Escape("Founder, Realty Systems Foundry")
            $hasAboutProfileBlock = $about.Content -match [regex]::Escape('class="about-profile-block"')
            $hasAboutProfileName = $about.Content -match [regex]::Escape('class="about-profile-name">Key Castro</p>')
            $hasWhatIDo = $about.Content -match [regex]::Escape('<h1>Technology built for real estate operations.</h1>')
            $approvedAboutDescription = "Realty Systems Foundry designs, builds, and manages custom software systems for real estate businesses. We help brokerages, teams, agents, property companies, and property managers organize operations, reduce manual work, and bring important workflows into one system."
            $hasApprovedAboutDescription = $about.Content -match [regex]::Escape($approvedAboutDescription)
            $hasAboutValueRow = ($about.Content -match [regex]::Escape("Custom Systems")) -and ($about.Content -match [regex]::Escape("Built around your workflow")) -and ($about.Content -match [regex]::Escape("Automation")) -and ($about.Content -match [regex]::Escape("Less manual work")) -and ($about.Content -match [regex]::Escape("Real Results")) -and ($about.Content -match [regex]::Escape("More time for what matters"))
            $hasAboutStoryFlow = (($about.Content | Select-String -Pattern 'class="about-story-index"' -AllMatches).Matches.Count -eq 5) -and ($about.Content -match [regex]::Escape("THE PROBLEMS WE HELP SOLVE")) -and ($about.Content -match [regex]::Escape("AUTOMATION")) -and ($about.Content -match [regex]::Escape("FEWER DISCONNECTED PLATFORMS")) -and ($about.Content -match [regex]::Escape("WHAT WE BUILD")) -and ($about.Content -match [regex]::Escape("HOW WE WORK"))
            $hasAboutPreservedDetails = ($about.Content -match [regex]::Escape("Missed follow-ups and deadlines")) -and ($about.Content -match [regex]::Escape("Software that does not fully fit")) -and ($about.Content -match [regex]::Escape("Recurring tasks and handoffs")) -and ($about.Content -match [regex]::Escape("The best option depends on the business.")) -and ($about.Content -match [regex]::Escape("Business-specific rules")) -and ($about.Content -match [regex]::Escape(">View Systems</a>"))
            $portraitLoads = ($portrait.StatusCode -eq 200) -and ($portrait.RawContentLength -gt 100000)
            $hasServicesPricingName = ($homePage.Content -match [regex]::Escape('>Services & Pricing</a>')) -and ($how.Content -match [regex]::Escape('<h1>Services & Pricing</h1>')) -and ($how.Content -match [regex]::Escape('<title>Services &amp; Pricing | Realty Systems Foundry</title>'))
            $hasHomeCreateSystemButton = ($homePage.Content -match [regex]::Escape('href="/contact">Create a New System</a>')) -and -not ($homePage.Content -match [regex]::Escape('>Tell Me What You Need</a>'))
            $hasHomeFeaturedCtas = ($homePage.Content -match [regex]::Escape('class="home-featured-action-link home-featured-action-link--primary" href="/system-templates"')) -and ($homePage.Content -match [regex]::Escape('Explore All Systems')) -and ($homePage.Content -match [regex]::Escape('class="home-featured-action-link home-featured-action-link--secondary" href="/services"')) -and ($homePage.Content -match [regex]::Escape('See Services & Pricing'))
            $hasApprovedHomeCtaMicrocopy = ($homePage.Content -match [regex]::Escape('READY TO SEE MORE?')) -and ($homePage.Content -match [regex]::Escape('NEED DETAILS?')) -and ($homePage.Content -match [regex]::Escape('PLAN')) -and ($homePage.Content -match [regex]::Escape('BUILD')) -and ($homePage.Content -match [regex]::Escape('ORGANIZE')) -and ($homePage.Content -match [regex]::Escape('GROW'))
            $hasHomeCtaDesignCss = ($siteCss.Content -match [regex]::Escape('.home-featured-actions-section')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-action-link--primary')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-action-link--secondary')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-edge--left')) -and ($siteCss.Content -match [regex]::Escape('.home-featured-edge--right'))
            $oldHomeCtaGone = -not ($homePage.Content -match [regex]::Escape('home-services-cta-link'))
            $oldHomeProcessGone = -not ($homePage.Content -match [regex]::Escape('How it works.')) -and -not ($homePage.Content -match [regex]::Escape('From your problem to a working system.')) -and -not ($homePage.Content -match [regex]::Escape('Tell me what you need.')) -and -not ($homePage.Content -match [regex]::Escape('Choose your system.')) -and -not ($homePage.Content -match [regex]::Escape('Choose who manages it.')) -and -not ($homePage.Content -match [regex]::Escape('class="home-process-list"'))
            $hasRebrand = ($homePage.Content -match [regex]::Escape('REALTY SYSTEMS FOUNDRY')) -and ($homePage.Content -match [regex]::Escape('We Build Custom Systems for Real Estate Businesses.')) -and ($about.Content -match [regex]::Escape('ABOUT REALTY SYSTEMS FOUNDRY')) -and ($about.Content -match [regex]::Escape('Founder, Realty Systems Foundry')) -and -not ($homePage.Content -match [regex]::Escape('I build simple systems for real estate businesses.'))
            if ($health.status -eq "ok" -and $health.version -eq $expectedVersion -and $hasRebrand -and $hasServicesPricingName -and $hasHomeCreateSystemButton -and $hasHomeFeaturedCtas -and $hasApprovedHomeCtaMicrocopy -and $hasHomeCtaDesignCss -and $oldHomeCtaGone -and $oldHomeProcessGone -and $hasStudentHousing -and $hasThreeSystems -and $hasStep1 -and $hasStep2 -and $hasNoStep3 -and $oldBuildStepGone -and $hasManagementStep -and $hasViewSystemsButton -and $hasRequestSystemButton -and $finalCtaGone -and $hasExistingSystemPrice -and $hasThreeHomePriceCards -and $hasThreePricedSystemCards -and $hasPurchaseBoundary -and $hasExistingSystemContact -and $hasAgreementPrice -and $oldExistingQuoteGone -and $hasUsdOnlyPublicPricing -and $hasPricing -and $oldPricingGone -and $hasMaintenanceBoundary -and $hasUpgradePricing -and $hasAboutAutomation -and $hasAboutSubscriptionValue -and $hasNewTagline -and $oldTaglineGone -and $hasAboutPortrait -and $hasAboutProfessionalTitle -and $hasAboutProfileBlock -and $hasAboutProfileName -and $hasWhatIDo -and $hasApprovedAboutDescription -and $hasAboutValueRow -and $hasAboutStoryFlow -and $hasAboutPreservedDetails -and $portraitLoads) {
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

    Write-Host "[I/9] Verifying private RSF Inbox and switching its local endpoint..." -ForegroundColor Yellow
    Test-PrivateInboxOnHost -BaseUrl $liveBase -TargetFolder $target

    # Switch the private local inbox endpoint only after the new public hostname
    # has been verified. The private token itself is never changed.
    $ownerConfigPath = Join-Path $target ".owner_inbox.json"
    if (Test-Path $ownerConfigPath) {
        try {
            $ownerConfig = Get-Content -LiteralPath $ownerConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($ownerConfig.token) {
                $ownerConfig.api_base = "$liveBase/__owner_api"
                $ownerConfig | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $ownerConfigPath -Encoding UTF8
                Write-Host "      Private RSF Inbox endpoint updated; token preserved." -ForegroundColor DarkGray
            }
        }
        catch {
            throw "The new Render hostname is live, but the private RSF Inbox endpoint could not be updated safely: $($_.Exception.Message)"
        }
    }

    Write-Host ""
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "  LIVE DEPLOYMENT VERIFIED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "======================================================" -ForegroundColor Green
    Write-Host "Version: $expectedVersion"
    Write-Host "Live site: $liveBase"
    Write-Host "Render service: $desiredServiceName ($activeServiceId)"
    Write-Host "Legacy rollback service retained: $legacyServiceName ($legacyServiceId)"
    Write-Host "Systems: 3 published systems confirmed"
    Write-Host "Student Housing system: confirmed LIVE"
    Write-Host "About automation/problem update: confirmed LIVE"
    Write-Host "Approved About profile: confirmed LIVE"
    Write-Host "About lower story organization: confirmed LIVE"
    Write-Host "Home hero Create a New System CTA: confirmed LIVE"
    Write-Host "Home featured-systems CTA redesign: confirmed LIVE"
    Write-Host "Explore All Systems + Services & Pricing CTA destinations: confirmed LIVE"
    Write-Host "Old Home three-step process: confirmed removed"
    Write-Host "Pricing/service information: confirmed LIVE"
    Write-Host "Existing system `$199 pricing: confirmed LIVE"
    Write-Host "Price by Agreement wording: confirmed LIVE"
    Write-Host "Realty Systems Foundry public brand: confirmed LIVE"
    Write-Host "Founder attribution: confirmed LIVE"
    Write-Host "Footer tagline: confirmed LIVE"
    Write-Host "Commit: $sha"
    Write-Host ""
}
finally {
    Pop-Location
}
