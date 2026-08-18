function Get-PokemonSearchDefaultConfigPath {
    $folder = Join-Path $HOME '.pokemonsearch'
    Join-Path $folder 'config.json'
}

function Get-PokemonSearchDefaultCollectionPath {
    $folder = Join-Path $HOME '.pokemonsearch'
    Join-Path $folder 'collection.json'
}

function Get-PokemonSearchSettings {
    if ($script:PokemonSearchRuntimeConfig) {
        return $script:PokemonSearchRuntimeConfig
    }

    $configPath = Get-PokemonSearchDefaultConfigPath
    $saved = $null
    if (Test-Path $configPath) {
        try {
            $saved = Get-Content -Path $configPath -Raw | ConvertFrom-Json
        }
        catch {
            throw "PokemonSearch configuration is invalid JSON: $configPath. $($_.Exception.Message)"
        }
    }

    $settings = [ordered]@{
        ConfigPath             = $configPath
        PokemonTcgApiKey       = if ($env:POKEMONTCG_API_KEY) { $env:POKEMONTCG_API_KEY } else { $saved.PokemonTcgApiKey }
        PriceChartingToken     = if ($env:PRICECHARTING_TOKEN) { $env:PRICECHARTING_TOKEN } else { $saved.PriceChartingToken }
        EbayClientId           = if ($env:EBAY_CLIENT_ID) { $env:EBAY_CLIENT_ID } else { $saved.EbayClientId }
        EbayClientSecret       = if ($env:EBAY_CLIENT_SECRET) { $env:EBAY_CLIENT_SECRET } else { $saved.EbayClientSecret }
        EbayMarketplaceId      = if ($saved.EbayMarketplaceId) { $saved.EbayMarketplaceId } else { 'EBAY_US' }
        CacheMinutes           = if ($null -ne $saved.CacheMinutes) { [int]$saved.CacheMinutes } else { 30 }
        CollectionPath         = if ($saved.CollectionPath) { [string]$saved.CollectionPath } else { Get-PokemonSearchDefaultCollectionPath }
        TargetDiscountPercent  = if ($null -ne $saved.TargetDiscountPercent) { [double]$saved.TargetDiscountPercent } else { 20.0 }
        ExcellentBuyPercent    = if ($null -ne $saved.ExcellentBuyPercent) { [double]$saved.ExcellentBuyPercent } else { 28.0 }
        GoodBuyPercent         = if ($null -ne $saved.GoodBuyPercent) { [double]$saved.GoodBuyPercent } else { 20.0 }
        AcceptableBuyPercent   = if ($null -ne $saved.AcceptableBuyPercent) { [double]$saved.AcceptableBuyPercent } else { 12.0 }
        PythonPath             = if ($saved.PythonPath) { [string]$saved.PythonPath } else { 'python' }
        TesseractPath          = if ($saved.TesseractPath) { [string]$saved.TesseractPath } else { $null }
    }

    $script:PokemonSearchRuntimeConfig = [pscustomobject]$settings
    return $script:PokemonSearchRuntimeConfig
}

function Reset-PokemonSearchSettingsCache {
    $script:PokemonSearchRuntimeConfig = $null
}

function Get-PokemonSearchDefaultWatchlistPath {
    $folder = Join-Path $HOME '.pokemonsearch'
    Join-Path $folder 'watchlist.json'
}

function Get-PokemonSearchDefaultPriceHistoryPath {
    $folder = Join-Path $HOME '.pokemonsearch'
    Join-Path $folder 'price-history.jsonl'
}
