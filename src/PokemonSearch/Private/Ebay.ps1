function Get-EbayApplicationAccessToken {
    $settings = Get-PokemonSearchSettings
    if (-not $settings.EbayClientId -or -not $settings.EbayClientSecret) {
        throw 'eBay is not configured. Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET or use Set-PokemonSearchConfig.'
    }

    if ($script:EbayAccessTokenCache -and $script:EbayAccessTokenCache.ExpiresAt -gt (Get-Date).AddMinutes(2)) {
        return $script:EbayAccessTokenCache.Token
    }

    $pair = '{0}:{1}' -f $settings.EbayClientId, $settings.EbayClientSecret
    $basic = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($pair))
    $headers = @{ Authorization = "Basic $basic" }
    $body = 'grant_type=client_credentials&scope=' + [uri]::EscapeDataString('https://api.ebay.com/oauth/api_scope')
    $response = Invoke-PokemonSearchRestMethod -Uri 'https://api.ebay.com/identity/v1/oauth2/token' -Method POST -Headers $headers -Body $body -ContentType 'application/x-www-form-urlencoded'

    $script:EbayAccessTokenCache = [pscustomobject]@{
        Token     = $response.access_token
        ExpiresAt = (Get-Date).AddSeconds([int]$response.expires_in)
    }
    $response.access_token
}

function Invoke-EbayBrowseSearchInternal {
    param([Parameter(Mandatory)][string]$Query,[ValidateRange(1,200)][int]$Limit = 20)
    $settings = Get-PokemonSearchSettings
    $token = Get-EbayApplicationAccessToken
    $headers = @{ Authorization = "Bearer $token"; 'X-EBAY-C-MARKETPLACE-ID' = $settings.EbayMarketplaceId }
    $params = @{ q=$Query; limit=$Limit }
    $uri = 'https://api.ebay.com/buy/browse/v1/item_summary/search?' + (ConvertTo-PokemonSearchQueryString -Parameters $params)
    $cacheIdentity = 'ebay:{0}:{1}:{2}' -f $settings.EbayMarketplaceId, $Query, $Limit
    Invoke-PokemonSearchRestMethod -Uri $uri -Headers $headers -CacheMinutes ([math]::Min($settings.CacheMinutes, 10)) -CacheIdentity $cacheIdentity
}

function Invoke-EbayImageSearchInternal {
    param([Parameter(Mandatory)][string]$ImagePath,[ValidateRange(1,200)][int]$Limit = 20)
    if (-not (Test-Path $ImagePath -PathType Leaf)) { throw "Image not found: $ImagePath" }
    $settings = Get-PokemonSearchSettings
    $token = Get-EbayApplicationAccessToken
    $headers = @{ Authorization = "Bearer $token"; 'X-EBAY-C-MARKETPLACE-ID' = $settings.EbayMarketplaceId }
    $bytes = [IO.File]::ReadAllBytes((Resolve-Path $ImagePath))
    $body = @{ image = [Convert]::ToBase64String($bytes) } | ConvertTo-Json -Compress
    $uri = "https://api.ebay.com/buy/browse/v1/item_summary/search_by_image?limit=$Limit"
    Invoke-PokemonSearchRestMethod -Uri $uri -Method POST -Headers $headers -Body $body -ContentType 'application/json'
}

function ConvertFrom-EbayItemSummary {
    param([Parameter(Mandatory)]$Item)
    $shipping = 0.0
    if ($Item.shippingOptions) {
        $firstShipping = @($Item.shippingOptions)[0]
        if ($firstShipping.shippingCost.value) { $shipping = [double]$firstShipping.shippingCost.value }
    }
    $price = if ($Item.price.value) { [double]$Item.price.value } else { $null }
    [pscustomobject]@{
        Provider='eBay Active'; ItemId=$Item.itemId; Title=$Item.title; Price=$price; Shipping=$shipping
        DeliveredPrice=if ($null -ne $price) { [math]::Round($price + $shipping, 2) } else { $null }
        Currency=$Item.price.currency; BuyingOptions=@($Item.buyingOptions); ItemUrl=$Item.itemWebUrl; ImageUrl=$Item.image.imageUrl
        Seller=$Item.seller.username; SellerFeedback=$Item.seller.feedbackPercentage; ItemEndDate=$Item.itemEndDate; Raw=$Item
    }
}
