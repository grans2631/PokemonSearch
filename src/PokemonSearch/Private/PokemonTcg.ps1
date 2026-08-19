function Invoke-PokemonTcgRequest {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Endpoint,
        [hashtable]$Query,
        [switch]$BypassCache
    )

    $settings = Get-PokemonSearchSettings
    $base = 'https://api.pokemontcg.io/v2'
    $uri = "$base/$($Endpoint.TrimStart('/'))"
    $queryString = ConvertTo-PokemonSearchQueryString -Parameters $Query
    if ($queryString) { $uri = "$uri`?$queryString" }

    $headers = @{}
    if ($settings.PokemonTcgApiKey) { $headers['X-Api-Key'] = $settings.PokemonTcgApiKey }

    Invoke-PokemonSearchRestMethod -Uri $uri -Headers $headers -CacheMinutes $settings.CacheMinutes -BypassCache:$BypassCache
}

function Normalize-PokemonCardNumber {
    param([string]$Number)

    if ([string]::IsNullOrWhiteSpace($Number)) { return $null }

    $normalized = $Number.Trim()
    $normalized = $normalized -replace '^#\s*', ''

    # Printed collector numbers are commonly shown as 233/091. The API's
    # card.number value is the numerator only, so search on 233.
    if ($normalized -match '/') {
        $normalized = ($normalized -split '/', 2)[0].Trim()
    }

    $normalized
}

function New-PokemonTcgSearchQuery {
    param([string]$Name,[string]$SetName,[string]$SetId,[string]$Number,[string]$Rarity)

    $normalizedNumber = Normalize-PokemonCardNumber -Number $Number
    $clauses = New-Object 'System.Collections.Generic.List[string]'
    foreach ($pair in @(
        @{ Field='name'; Value=$Name },
        @{ Field='set.name'; Value=$SetName },
        @{ Field='set.id'; Value=$SetId },
        @{ Field='number'; Value=$normalizedNumber },
        @{ Field='rarity'; Value=$Rarity }
    )) {
        if (-not $pair.Value) { continue }

        $safe = ([string]$pair.Value).Replace('"','\"')

        # The Pokemon TCG API documentation uses unquoted values for
        # single tokens (name:Pikachu) and quotes for phrases
        # (name:"Mewtwo ex").
        if ($safe -match '\s') {
            $clauses.Add(('{0}:"{1}"' -f $pair.Field, $safe))
        }
        else {
            $clauses.Add(('{0}:{1}' -f $pair.Field, $safe))
        }
    }

    $clauses -join ' '
}

function ConvertFrom-PokemonTcgCard {
    param([Parameter(Mandatory)]$Card)
    $variants = @()
    if ($Card.tcgplayer -and $Card.tcgplayer.prices) {
        foreach ($property in $Card.tcgplayer.prices.PSObject.Properties) {
            $price = $property.Value
            $variants += [pscustomobject]@{
                Variant=$property.Name
                Low=$price.low
                Mid=$price.mid
                High=$price.high
                Market=$price.market
                DirectLow=$price.directLow
            }
        }
    }

    [pscustomobject]@{
        Id=$Card.id
        Name=$Card.name
        SetId=$Card.set.id
        SetName=$Card.set.name
        Series=$Card.set.series
        Number=$Card.number
        Rarity=$Card.rarity
        Supertype=$Card.supertype
        Subtypes=@($Card.subtypes)
        Artist=$Card.artist
        ImageSmall=$Card.images.small
        ImageLarge=$Card.images.large
        TcgPlayerUrl=$Card.tcgplayer.url
        TcgPlayerUpdated=$Card.tcgplayer.updatedAt
        PriceVariants=$variants
        Raw=$Card
    }
}

function Get-PokemonPreferredVariantPrice {
    param([Parameter(Mandatory)]$Card,[string]$Variant)
    $variants = @($Card.PriceVariants)
    if ($Variant) { return $variants | Where-Object Variant -eq $Variant | Select-Object -First 1 }
    foreach ($preferred in @('holofoil','normal','reverseHolofoil','1stEditionHolofoil','unlimitedHolofoil')) {
        $match = $variants | Where-Object Variant -eq $preferred | Select-Object -First 1
        if ($match) { return $match }
    }
    $variants | Where-Object { $null -ne $_.Market } | Sort-Object Market -Descending | Select-Object -First 1
}
