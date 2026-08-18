function Get-PriceChartingProductInternal {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$Query)

    $settings = Get-PokemonSearchSettings
    if (-not $settings.PriceChartingToken) {
        throw 'PriceCharting is not configured. Set PRICECHARTING_TOKEN or run Set-PokemonSearchConfig -PriceChartingToken <token>.'
    }

    $params = @{ t = $settings.PriceChartingToken; q = $Query }
    $uri = 'https://www.pricecharting.com/api/product?' + (ConvertTo-PokemonSearchQueryString -Parameters $params)
    $response = Invoke-PokemonSearchRestMethod -Uri $uri -CacheMinutes $settings.CacheMinutes -CacheIdentity ("pricecharting:$Query")
    if ($response.status -ne 'success') { throw "PriceCharting returned an error: $($response.'error-message')" }

    [pscustomobject]@{
        Provider='PriceCharting'; ProductId=$response.id; ProductName=$response.'product-name'; ConsoleName=$response.'console-name'
        Ungraded=if ($null -ne $response.'loose-price') { [math]::Round($response.'loose-price' / 100, 2) } else { $null }
        Grade8=if ($null -ne $response.'new-price') { [math]::Round($response.'new-price' / 100, 2) } else { $null }
        Grade9=if ($null -ne $response.'graded-price') { [math]::Round($response.'graded-price' / 100, 2) } else { $null }
        Grade95=if ($null -ne $response.'box-only-price') { [math]::Round($response.'box-only-price' / 100, 2) } else { $null }
        Psa10=if ($null -ne $response.'manual-only-price') { [math]::Round($response.'manual-only-price' / 100, 2) } else { $null }
        Bgs10=if ($null -ne $response.'bgs-10-price') { [math]::Round($response.'bgs-10-price' / 100, 2) } else { $null }
        Raw=$response
    }
}
