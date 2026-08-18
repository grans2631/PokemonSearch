function Get-PokemonSearchConfig {
    [CmdletBinding()]
    param([switch]$RevealSecrets)

    $s = Get-PokemonSearchSettings
    [pscustomobject]@{
        ConfigPath            = $s.ConfigPath
        PokemonTcgApiKey      = if ($RevealSecrets) { $s.PokemonTcgApiKey } else { [bool]$s.PokemonTcgApiKey }
        PriceChartingToken    = if ($RevealSecrets) { $s.PriceChartingToken } else { [bool]$s.PriceChartingToken }
        EbayClientId          = if ($RevealSecrets) { $s.EbayClientId } else { [bool]$s.EbayClientId }
        EbayClientSecret      = if ($RevealSecrets) { $s.EbayClientSecret } else { [bool]$s.EbayClientSecret }
        EbayMarketplaceId     = $s.EbayMarketplaceId
        CacheMinutes          = $s.CacheMinutes
        CollectionPath        = $s.CollectionPath
        TargetDiscountPercent = $s.TargetDiscountPercent
        ExcellentBuyPercent   = $s.ExcellentBuyPercent
        GoodBuyPercent        = $s.GoodBuyPercent
        AcceptableBuyPercent  = $s.AcceptableBuyPercent
        PythonPath            = $s.PythonPath
        TesseractPath         = $s.TesseractPath
    }
}

function Set-PokemonSearchConfig {
    [CmdletBinding(SupportsShouldProcess)]
    param(
        [string]$PokemonTcgApiKey,[string]$PriceChartingToken,[string]$EbayClientId,[string]$EbayClientSecret,[string]$EbayMarketplaceId,
        [ValidateRange(0,1440)][int]$CacheMinutes,[string]$CollectionPath,[ValidateRange(0,100)][double]$TargetDiscountPercent,
        [ValidateRange(0,100)][double]$ExcellentBuyPercent,[ValidateRange(0,100)][double]$GoodBuyPercent,
        [ValidateRange(0,100)][double]$AcceptableBuyPercent,[string]$PythonPath,[string]$TesseractPath
    )

    $configPath = Get-PokemonSearchDefaultConfigPath
    $existing = @{}
    if (Test-Path $configPath) {
        $obj = Get-Content $configPath -Raw | ConvertFrom-Json
        foreach ($p in $obj.PSObject.Properties) { $existing[$p.Name] = $p.Value }
    }
    foreach ($name in $PSBoundParameters.Keys) {
        if ($name -in @('WhatIf','Confirm')) { continue }
        $existing[$name] = $PSBoundParameters[$name]
    }
    $parent = Split-Path $configPath -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    if ($PSCmdlet.ShouldProcess($configPath, 'Write PokemonSearch local configuration')) {
        [pscustomobject]$existing | ConvertTo-Json -Depth 10 | Set-Content -Path $configPath -Encoding utf8
        Reset-PokemonSearchSettingsCache
        Get-PokemonSearchConfig
    }
}
