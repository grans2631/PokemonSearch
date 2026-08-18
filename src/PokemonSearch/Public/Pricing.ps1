function Get-PokemonCardPrice {
    [CmdletBinding(DefaultParameterSetName='Id')]
    param(
        [Parameter(Mandatory,ParameterSetName='Id')][string]$Id,
        [Parameter(Mandatory,ParameterSetName='Search')][string]$Name,
        [Parameter(ParameterSetName='Search')][string]$SetName,
        [Parameter(ParameterSetName='Search')][string]$SetId,
        [Parameter(ParameterSetName='Search')][string]$Number,
        [ValidateSet('PokemonTCG','PriceCharting','eBay','All')][string]$Provider = 'PokemonTCG',
        [string]$Variant,
        [ValidateRange(1,100)][int]$EbayLimit = 20,
        [switch]$BypassCache
    )

    $card = if ($PSCmdlet.ParameterSetName -eq 'Id') { Get-PokemonCard -Id $Id -BypassCache:$BypassCache } else { Get-PokemonCard -Name $Name -SetName $SetName -SetId $SetId -Number $Number -BypassCache:$BypassCache }
    if (-not $card) { return }
    $providers = if ($Provider -eq 'All') { @('PokemonTCG','PriceCharting','eBay') } else { @($Provider) }
    foreach ($p in $providers) {
        switch ($p) {
            'PokemonTCG' {
                $variants = if ($Variant) { @($card.PriceVariants | Where-Object Variant -eq $Variant) } else { @($card.PriceVariants) }
                foreach ($price in $variants) {
                    [pscustomobject]@{ Provider='PokemonTCG/TCGplayer'; CardId=$card.Id; Name=$card.Name; SetName=$card.SetName; Number=$card.Number; Variant=$price.Variant; Low=$price.Low; Mid=$price.Mid; High=$price.High; Market=$price.Market; DirectLow=$price.DirectLow; UpdatedAt=$card.TcgPlayerUpdated; Url=$card.TcgPlayerUrl }
                }
            }
            'PriceCharting' {
                try { $query = @($card.Name, "#$($card.Number)", $card.SetName, 'Pokemon') -join ' '; Get-PriceChartingProductInternal -Query $query } catch { Write-Warning $_.Exception.Message }
            }
            'eBay' {
                try { Get-PokemonEbayListing -CardId $card.Id -Limit $EbayLimit } catch { Write-Warning $_.Exception.Message }
            }
        }
    }
}

function Get-PokemonBidRange {
    [CmdletBinding(DefaultParameterSetName='Id')]
    param(
        [Parameter(Mandatory,ParameterSetName='Id')][string]$Id,[Parameter(Mandatory,ParameterSetName='Search')][string]$Name,
        [Parameter(ParameterSetName='Search')][string]$SetName,[Parameter(ParameterSetName='Search')][string]$SetId,[Parameter(ParameterSetName='Search')][string]$Number,
        [string]$Variant,[ValidateRange(0,100)][double]$TargetDiscountPercent,[ValidateRange(0,100000)][double]$Shipping = 0,
        [ValidateRange(0,100)][double]$BuyerFeePercent = 0,[ValidateRange(0,100000)][double]$TaxEstimate = 0,[switch]$UsePriceCharting,[switch]$BypassCache
    )

    $settings = Get-PokemonSearchSettings
    if (-not $PSBoundParameters.ContainsKey('TargetDiscountPercent')) { $TargetDiscountPercent = $settings.TargetDiscountPercent }
    $card = if ($PSCmdlet.ParameterSetName -eq 'Id') { Get-PokemonCard -Id $Id -BypassCache:$BypassCache } else { Get-PokemonCard -Name $Name -SetName $SetName -SetId $SetId -Number $Number -BypassCache:$BypassCache }
    if (-not $card) { return }
    $tcg = Get-PokemonPreferredVariantPrice -Card $card -Variant $Variant
    $marketCandidates = [System.Collections.Generic.List[double]]::new()
    if ($tcg -and $null -ne $tcg.Market) { $marketCandidates.Add([double]$tcg.Market) }
    $pc = $null
    if ($UsePriceCharting) {
        try { $pc = Get-PriceChartingProductInternal -Query (@($card.Name, "#$($card.Number)", $card.SetName, 'Pokemon') -join ' '); if ($null -ne $pc.Ungraded) { $marketCandidates.Add([double]$pc.Ungraded) } } catch { Write-Warning $_.Exception.Message }
    }
    if ($marketCandidates.Count -eq 0) { throw 'No raw market price is available for this card/variant.' }
    $sorted = @($marketCandidates | Sort-Object)
    $market = if ($sorted.Count % 2 -eq 1) { $sorted[[math]::Floor($sorted.Count / 2)] } else { ($sorted[$sorted.Count/2 - 1] + $sorted[$sorted.Count/2]) / 2 }
    function NetBid([double]$Discount) {
        $maxAllIn = $market * (1 - ($Discount / 100)); $feeMultiplier = 1 + ($BuyerFeePercent / 100)
        [math]::Max(0, (($maxAllIn - $Shipping - $TaxEstimate) / $feeMultiplier))
    }
    $target = NetBid $TargetDiscountPercent
    [pscustomobject]@{
        CardId=$card.Id; Name=$card.Name; SetName=$card.SetName; Number=$card.Number; Variant=if ($tcg) { $tcg.Variant } else { $Variant }
        TcgPlayerMarket=if ($tcg) { $tcg.Market } else { $null }; PriceChartingUngraded=if ($pc) { $pc.Ungraded } else { $null }
        CalculatedMarket=[math]::Round($market,2); ExcellentBuyMaxBid=[math]::Round((NetBid $settings.ExcellentBuyPercent),2)
        GoodBuyMaxBid=[math]::Round((NetBid $settings.GoodBuyPercent),2); AcceptableBuyMaxBid=[math]::Round((NetBid $settings.AcceptableBuyPercent),2)
        RecommendedMaxBid=[math]::Round($target,2); TargetDiscountPercent=$TargetDiscountPercent; Shipping=$Shipping; BuyerFeePercent=$BuyerFeePercent; TaxEstimate=$TaxEstimate
        Method='Discount-to-market; active eBay listings are not treated as sold comps.'
    }
}
