function Import-PokemonCollection {
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)][string]$Path,[string]$DestinationPath,[switch]$Append)

    if (-not (Test-Path $Path -PathType Leaf)) { throw "File not found: $Path" }
    $ext = [IO.Path]::GetExtension($Path).ToLowerInvariant()
    switch ($ext) {
        '.csv' { $inputRows = @(Import-Csv -Path $Path) }
        '.json' { $inputRows = @(Get-Content -Path $Path -Raw | ConvertFrom-Json) }
        '.xlsx' {
            if (-not (Get-Module -ListAvailable -Name ImportExcel)) { throw 'Importing .xlsx requires the ImportExcel PowerShell module. Install-Module ImportExcel -Scope CurrentUser, or export the sheet as CSV.' }
            Import-Module ImportExcel -ErrorAction Stop
            $inputRows = @(Import-Excel -Path $Path)
        }
        default { throw 'Supported import formats: .csv, .json, .xlsx (with ImportExcel installed).' }
    }

    $records = @($inputRows | ForEach-Object { ConvertTo-PokemonCollectionRecord -InputObject $_ -Source ([IO.Path]::GetFileName($Path)) })
    $existing = if ($Append) { @(Read-PokemonCollectionInternal -Path $DestinationPath) } else { @() }
    $combined = @($existing) + @($records)
    if ($PSCmdlet.ShouldProcess(($DestinationPath ?? (Get-PokemonSearchSettings).CollectionPath), "Import $($records.Count) Pokemon card records")) {
        $written = Write-PokemonCollectionInternal -Collection $combined -Path $DestinationPath
        [pscustomobject]@{ Path=$written; Imported=$records.Count; Total=$combined.Count }
    }
}

function Add-PokemonCollectionCard {
    [CmdletBinding(SupportsShouldProcess,DefaultParameterSetName='Id')]
    param(
        [Parameter(Mandatory,ParameterSetName='Id')][string]$Id,[Parameter(Mandatory,ParameterSetName='Search')][string]$Name,
        [Parameter(ParameterSetName='Search')][string]$SetName,[Parameter(ParameterSetName='Search')][string]$SetId,[Parameter(ParameterSetName='Search')][string]$Number,
        [string]$Variant,[string]$Condition = 'Near Mint',[string]$Grade,[ValidateRange(1,9999)][int]$Quantity = 1,[double]$PurchasePrice,[string]$Notes,[string]$CollectionPath
    )
    $card = if ($PSCmdlet.ParameterSetName -eq 'Id') { Get-PokemonCard -Id $Id } else { Get-PokemonCard -Name $Name -SetName $SetName -SetId $SetId -Number $Number }
    if (-not $card) { return }
    $record = [pscustomobject]@{
        CardId=$card.Id; Name=$card.Name; SetId=$card.SetId; SetName=$card.SetName; Number=$card.Number; Variant=$Variant; Condition=$Condition; Grade=$Grade; Quantity=$Quantity
        PurchasePrice=if ($PSBoundParameters.ContainsKey('PurchasePrice')) { $PurchasePrice } else { $null }; Notes=$Notes; Source='Add-PokemonCollectionCard'; AddedAt=(Get-Date).ToString('o')
    }
    $collection = @(Read-PokemonCollectionInternal -Path $CollectionPath) + @($record)
    if ($PSCmdlet.ShouldProcess($card.Id, 'Add card to Pokemon collection')) {
        Write-PokemonCollectionInternal -Collection $collection -Path $CollectionPath | Out-Null
        $record
    }
}

function Get-PokemonCollectionValue {
    [CmdletBinding()]
    param([string]$CollectionPath,[switch]$IncludeItems,[switch]$BypassCache)
    $collection = @(Read-PokemonCollectionInternal -Path $CollectionPath)
    $items = @()
    foreach ($row in $collection) {
        $card = $null
        if ($row.CardId) { $card = Get-PokemonCard -Id $row.CardId -BypassCache:$BypassCache }
        elseif ($row.Name) { $card = Get-PokemonCard -Name $row.Name -SetId $row.SetId -SetName $row.SetName -Number $row.Number -BypassCache:$BypassCache }
        if (-not $card) { continue }
        $price = Get-PokemonPreferredVariantPrice -Card $card -Variant $row.Variant
        $market = if ($price) { [double]($price.Market ?? 0) } else { 0 }
        $quantity = if ($row.Quantity) { [int]$row.Quantity } else { 1 }
        $items += [pscustomobject]@{
            CardId=$card.Id; Name=$card.Name; SetName=$card.SetName; Number=$card.Number; Variant=if ($price) {$price.Variant}else{$row.Variant}
            Quantity=$quantity; MarketEach=[math]::Round($market,2); MarketTotal=[math]::Round($market*$quantity,2)
            CostEach=$row.PurchasePrice; CostTotal=if ($null -ne $row.PurchasePrice) {[math]::Round([double]$row.PurchasePrice*$quantity,2)}else{$null}
        }
    }
    $marketTotal = ($items | Measure-Object MarketTotal -Sum).Sum
    $costRows = @($items | Where-Object { $null -ne $_.CostTotal })
    $costTotal = if ($costRows.Count) { ($costRows | Measure-Object CostTotal -Sum).Sum } else { $null }
    $summary = [pscustomobject]@{
        Records=$collection.Count; Quantity=(($collection | Measure-Object Quantity -Sum).Sum ?? 0); PricedRecords=$items.Count; MarketValue=[math]::Round(($marketTotal ?? 0),2)
        KnownCostBasis=if ($null -ne $costTotal) {[math]::Round($costTotal,2)}else{$null}; UnrealizedDifference=if ($null -ne $costTotal) {[math]::Round(($marketTotal-$costTotal),2)}else{$null}
    }
    if ($IncludeItems) { [pscustomobject]@{ Summary=$summary; Items=$items } } else { $summary }
}

function Get-PokemonSetChecklist {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$SetId,[string]$CollectionPath,[switch]$IncludePrices,[switch]$MissingOnly,[switch]$BypassCache)
    $response = Invoke-PokemonTcgRequest -Endpoint 'cards' -Query @{ q="set.id:`"$SetId`""; pageSize=250 } -BypassCache:$BypassCache
    $owned = @(Read-PokemonCollectionInternal -Path $CollectionPath)
    foreach ($rawCard in @($response.data)) {
        $card = ConvertFrom-PokemonTcgCard -Card $rawCard
        $matches = @($owned | Where-Object { ($_.CardId -and $_.CardId -eq $card.Id) -or ($_.SetId -eq $card.SetId -and [string]$_.Number -eq [string]$card.Number) })
        $qty = (($matches | Measure-Object Quantity -Sum).Sum ?? 0)
        if ($MissingOnly -and $qty -gt 0) { continue }
        $preferred = if ($IncludePrices) { Get-PokemonPreferredVariantPrice -Card $card } else { $null }
        [pscustomobject]@{ Number=$card.Number; Name=$card.Name; Rarity=$card.Rarity; Owned=($qty -gt 0); Quantity=$qty; Market=if ($preferred) {$preferred.Market}else{$null}; Variant=if ($preferred) {$preferred.Variant}else{$null}; CardId=$card.Id; Image=$card.ImageSmall }
    }
}
