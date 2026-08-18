function Get-PokemonEbayListing {
    [CmdletBinding(DefaultParameterSetName='Query')]
    param(
        [Parameter(Mandatory,ParameterSetName='Query',Position=0)][string]$Query,
        [Parameter(Mandatory,ParameterSetName='Card')][string]$CardId,
        [ValidateRange(1,200)][int]$Limit = 20
    )

    if ($PSCmdlet.ParameterSetName -eq 'Card') {
        $card = Get-PokemonCard -Id $CardId
        if (-not $card) { return }
        $Query = @($card.Name, "#$($card.Number)", $card.SetName, 'Pokemon card') -join ' '
    }

    $response = Invoke-EbayBrowseSearchInternal -Query $Query -Limit $Limit
    foreach ($item in @($response.itemSummaries)) { ConvertFrom-EbayItemSummary -Item $item }
}
