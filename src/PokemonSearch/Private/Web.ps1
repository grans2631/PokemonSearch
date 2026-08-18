function Get-PokemonSearchCacheRoot {
    $root = Join-Path ([System.IO.Path]::GetTempPath()) 'PokemonSearchCache'
    if (-not (Test-Path $root)) {
        New-Item -ItemType Directory -Path $root -Force | Out-Null
    }
    $root
}

function Get-PokemonSearchHash {
    param([Parameter(Mandatory)][string]$Value)
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Value)
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Invoke-PokemonSearchRestMethod {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Uri,
        [ValidateSet('GET','POST')][string]$Method = 'GET',
        [hashtable]$Headers,
        [object]$Body,
        [string]$ContentType = 'application/json',
        [int]$CacheMinutes = 0,
        [switch]$BypassCache,
        [string]$CacheIdentity,
        [ValidateRange(1,5)][int]$MaxAttempts = 3
    )

    $canCache = $Method -eq 'GET' -and $CacheMinutes -gt 0 -and -not $BypassCache
    $cacheFile = $null
    if ($canCache) {
        $identity = if ($CacheIdentity) { $CacheIdentity } else { $Uri }
        $cacheFile = Join-Path (Get-PokemonSearchCacheRoot) ((Get-PokemonSearchHash $identity) + '.json')
        if (Test-Path $cacheFile) {
            $age = (Get-Date) - (Get-Item $cacheFile).LastWriteTime
            if ($age.TotalMinutes -lt $CacheMinutes) {
                return (Get-Content $cacheFile -Raw | ConvertFrom-Json)
            }
        }
    }

    $params = @{
        Uri         = $Uri
        Method      = $Method
        ErrorAction = 'Stop'
    }
    if ($Headers) { $params.Headers = $Headers }
    if ($null -ne $Body) { $params.Body = $Body }
    if ($ContentType) { $params.ContentType = $ContentType }

    $response = $null
    $lastError = $null
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $response = Invoke-RestMethod @params
            $lastError = $null
            break
        }
        catch {
            $lastError = $_
            $statusCode = $null
            try {
                if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
                    $statusCode = [int]$_.Exception.Response.StatusCode
                }
            }
            catch { }

            $isTransient = $statusCode -in @(408,429,500,502,503,504)
            if (-not $isTransient -or $attempt -ge $MaxAttempts) {
                break
            }

            Start-Sleep -Seconds ([int][math]::Pow(2, $attempt - 1))
        }
    }

    if ($lastError) {
        $detail = $lastError.ErrorDetails.Message
        if (-not $detail) { $detail = $lastError.Exception.Message }
        throw "Request failed after $MaxAttempts attempt(s): $Method $Uri`n$detail"
    }

    if ($canCache -and $cacheFile) {
        $response | ConvertTo-Json -Depth 100 | Set-Content -Path $cacheFile -Encoding utf8
    }
    $response
}

function ConvertTo-PokemonSearchQueryString {
    param([hashtable]$Parameters)
    if (-not $Parameters -or $Parameters.Count -eq 0) { return '' }
    ($Parameters.GetEnumerator() | Sort-Object Name | ForEach-Object {
        '{0}={1}' -f [uri]::EscapeDataString([string]$_.Key), [uri]::EscapeDataString([string]$_.Value)
    }) -join '&'
}
