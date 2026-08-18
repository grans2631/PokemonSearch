function Update-PokemonPriceHistory {
    [CmdletBinding(DefaultParameterSetName='Id')]
    param(
        [Parameter(Mandatory,ParameterSetName='Id',ValueFromPipelineByPropertyName)][string[]]$Id,
        [Parameter(Mandatory,ParameterSetName='Search')][string]$Name,
        [Parameter(ParameterSetName='Search')][string]$SetName,
        [Parameter(ParameterSetName='Search')][string]$SetId,
        [Parameter(ParameterSetName='Search')][string]$Number,
        [string]$Variant,[string]$HistoryPath,[switch]$BypassCache
    )
    begin {
        if (-not $HistoryPath) { $HistoryPath = Get-PokemonSearchDefaultPriceHistoryPath }
        $parent = Split-Path $HistoryPath -Parent
        if ($parent -and -not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
        $written = [System.Collections.Generic.List[object]]::new()
    }
    process {
        $cards = if ($PSCmdlet.ParameterSetName -eq 'Id') { foreach ($cardId in $Id) { Get-PokemonCard -Id $cardId -BypassCache:$BypassCache } } else { Get-PokemonCard -Name $Name -SetName $SetName -SetId $SetId -Number $Number -BypassCache:$BypassCache }
        foreach ($card in @($cards)) {
            if (-not $card) { continue }
            $variants = if ($Variant) { @($card.PriceVariants | Where-Object Variant -eq $Variant) } else { @($card.PriceVariants) }
            foreach ($price in $variants) {
                $row = [pscustomobject]@{
                    Timestamp=(Get-Date).ToUniversalTime().ToString('o'); CardId=$card.Id; Name=$card.Name; SetId=$card.SetId; SetName=$card.SetName; Number=$card.Number
                    Variant=$price.Variant; Low=$price.Low; Mid=$price.Mid; High=$price.High; Market=$price.Market; DirectLow=$price.DirectLow
                    Source='PokemonTCG/TCGplayer'; SourceUpdatedAt=$card.TcgPlayerUpdated
                }
                ($row | ConvertTo-Json -Compress) | Add-Content -Path $HistoryPath -Encoding utf8
                $written.Add($row)
            }
        }
    }
    end { @($written) }
}

function Get-PokemonPriceHistory {
    [CmdletBinding()]
    param([string]$Id,[string]$Name,[string]$Variant,[string]$HistoryPath,[datetime]$Since)
    if (-not $HistoryPath) { $HistoryPath = Get-PokemonSearchDefaultPriceHistoryPath }
    if (-not (Test-Path $HistoryPath)) { return @() }
    Get-Content $HistoryPath | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | ForEach-Object { $_ | ConvertFrom-Json } | Where-Object {
        (-not $Id -or $_.CardId -eq $Id) -and (-not $Name -or $_.Name -like "*$Name*") -and (-not $Variant -or $_.Variant -eq $Variant) -and
        (-not $PSBoundParameters.ContainsKey('Since') -or [datetime]$_.Timestamp -ge $Since)
    } | Sort-Object Timestamp
}

function Add-PokemonWatchCard {
    [CmdletBinding(SupportsShouldProcess,DefaultParameterSetName='Id')]
    param(
        [Parameter(Mandatory,ParameterSetName='Id')][string]$Id,[Parameter(Mandatory,ParameterSetName='Search')][string]$Name,
        [Parameter(ParameterSetName='Search')][string]$SetName,[Parameter(ParameterSetName='Search')][string]$SetId,[Parameter(ParameterSetName='Search')][string]$Number,
        [string]$Variant,[double]$TargetPrice,[double]$MaxBid,[string]$Notes,[string]$WatchlistPath
    )
    $card = if ($PSCmdlet.ParameterSetName -eq 'Id') { Get-PokemonCard -Id $Id } else { Get-PokemonCard -Name $Name -SetName $SetName -SetId $SetId -Number $Number }
    if (-not $card) { return }
    $preferred = Get-PokemonPreferredVariantPrice -Card $card -Variant $Variant
    if (-not $PSBoundParameters.ContainsKey('TargetPrice') -and $preferred -and $null -ne $preferred.Market) {
        $settings = Get-PokemonSearchSettings
        $TargetPrice = [math]::Round(([double]$preferred.Market * (1 - $settings.GoodBuyPercent / 100)),2)
    }
    if (-not $PSBoundParameters.ContainsKey('MaxBid')) {
        try { $MaxBid = (Get-PokemonBidRange -Id $card.Id -Variant $Variant).RecommendedMaxBid } catch { $MaxBid = $null }
    }
    $watch = @(Read-PokemonWatchlistInternal -Path $WatchlistPath)
    $watch = @($watch | Where-Object { -not ($_.CardId -eq $card.Id -and [string]$_.Variant -eq [string]$Variant) })
    $row = [pscustomobject]@{
        CardId=$card.Id; Name=$card.Name; SetId=$card.SetId; SetName=$card.SetName; Number=$card.Number
        Variant=if($Variant){$Variant}elseif($preferred){$preferred.Variant}else{$null}
        TargetPrice=if($PSBoundParameters.ContainsKey('TargetPrice') -or $null -ne $TargetPrice){$TargetPrice}else{$null}
        MaxBid=$MaxBid; Notes=$Notes; AddedAt=(Get-Date).ToString('o')
    }
    $watch += $row
    if ($PSCmdlet.ShouldProcess($card.Id, 'Add or update Pokemon watch card')) {
        Write-PokemonWatchlistInternal -Watchlist $watch -Path $WatchlistPath | Out-Null
        $row
    }
}

function Remove-PokemonWatchCard {
    [CmdletBinding(SupportsShouldProcess)]
    param([Parameter(Mandatory)][string]$Id,[string]$Variant,[string]$WatchlistPath)
    $watch = @(Read-PokemonWatchlistInternal -Path $WatchlistPath)
    $new = @($watch | Where-Object { if ($Variant) { -not ($_.CardId -eq $Id -and $_.Variant -eq $Variant) } else { $_.CardId -ne $Id } })
    if ($PSCmdlet.ShouldProcess($Id, 'Remove Pokemon watch card')) {
        Write-PokemonWatchlistInternal -Watchlist $new -Path $WatchlistPath | Out-Null
        [pscustomobject]@{ Removed=($watch.Count-$new.Count); Remaining=$new.Count }
    }
}

function Get-PokemonWatchlist {
    [CmdletBinding()]
    param([string]$WatchlistPath,[switch]$Refresh,[switch]$RecordHistory,[switch]$BypassCache)
    $watch = @(Read-PokemonWatchlistInternal -Path $WatchlistPath)
    foreach ($row in $watch) {
        if (-not $Refresh) { $row; continue }
        $card = Get-PokemonCard -Id $row.CardId -BypassCache:$BypassCache
        $price = if ($card) { Get-PokemonPreferredVariantPrice -Card $card -Variant $row.Variant } else { $null }
        $market = if ($price -and $null -ne $price.Market) { [double]$price.Market } else { $null }
        if ($RecordHistory -and $card) { Update-PokemonPriceHistory -Id $card.Id -Variant $price.Variant -BypassCache:$BypassCache | Out-Null }
        [pscustomobject]@{
            CardId=$row.CardId; Name=$row.Name; SetName=$row.SetName; Number=$row.Number; Variant=$row.Variant; TargetPrice=$row.TargetPrice; MaxBid=$row.MaxBid; Market=$market
            AtOrBelowTarget=if($null -ne $market -and $null -ne $row.TargetPrice){$market -le [double]$row.TargetPrice}else{$null}
            DifferenceToTarget=if($null -ne $market -and $null -ne $row.TargetPrice){[math]::Round($market-[double]$row.TargetPrice,2)}else{$null}
            Notes=$row.Notes; AddedAt=$row.AddedAt
        }
    }
}
