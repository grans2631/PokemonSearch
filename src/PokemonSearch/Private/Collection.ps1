function Read-PokemonCollectionInternal {
    param([string]$Path)
    $settings = Get-PokemonSearchSettings
    if (-not $Path) { $Path = $settings.CollectionPath }
    if (-not (Test-Path $Path)) { return @() }
    $raw = Get-Content -Path $Path -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) { return @() }
    @($raw | ConvertFrom-Json)
}

function Write-PokemonCollectionInternal {
    param([Parameter(Mandatory)][array]$Collection,[string]$Path)
    $settings = Get-PokemonSearchSettings
    if (-not $Path) { $Path = $settings.CollectionPath }
    $parent = Split-Path -Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    @($Collection) | ConvertTo-Json -Depth 20 | Set-Content -Path $Path -Encoding utf8
    $Path
}

function ConvertTo-PokemonCollectionRecord {
    param([Parameter(Mandatory)]$InputObject,[string]$Source = 'Import')

    function Pick([object]$obj, [string[]]$names) {
        foreach ($name in $names) {
            $prop = $obj.PSObject.Properties[$name]
            if ($prop -and $null -ne $prop.Value -and [string]$prop.Value -ne '') { return $prop.Value }
        }
        $null
    }

    [pscustomobject]@{
        CardId        = Pick $InputObject @('CardId','Id','card_id','productId')
        Name          = Pick $InputObject @('Name','CardName','Product Name','product_name')
        SetId         = Pick $InputObject @('SetId','Set ID','set_id')
        SetName       = Pick $InputObject @('SetName','Set','Set Name','set_name')
        Number        = Pick $InputObject @('Number','CardNumber','Card Number','number')
        Variant       = Pick $InputObject @('Variant','Printing','Foil','variant')
        Condition     = Pick $InputObject @('Condition','condition')
        Grade         = Pick $InputObject @('Grade','grade')
        Quantity      = if (Pick $InputObject @('Quantity','Qty','Count','quantity')) { [int](Pick $InputObject @('Quantity','Qty','Count','quantity')) } else { 1 }
        PurchasePrice = if (Pick $InputObject @('PurchasePrice','Purchase Price','Cost','cost')) { [double](Pick $InputObject @('PurchasePrice','Purchase Price','Cost','cost')) } else { $null }
        Notes         = Pick $InputObject @('Notes','Note','notes')
        Source        = $Source
        AddedAt       = (Get-Date).ToString('o')
    }
}

function Read-PokemonWatchlistInternal {
    param([string]$Path)
    if (-not $Path) { $Path = Get-PokemonSearchDefaultWatchlistPath }
    if (-not (Test-Path $Path)) { return @() }
    $raw = Get-Content $Path -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) { return @() }
    @($raw | ConvertFrom-Json)
}

function Write-PokemonWatchlistInternal {
    param([Parameter(Mandatory)][array]$Watchlist,[string]$Path)
    if (-not $Path) { $Path = Get-PokemonSearchDefaultWatchlistPath }
    $parent = Split-Path $Path -Parent
    if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    @($Watchlist) | ConvertTo-Json -Depth 20 | Set-Content $Path -Encoding utf8
    $Path
}
