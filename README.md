# PokemonSearch

PowerShell toolkit for finding, identifying, pricing, bidding on, and tracking Pokemon trading cards.

The project is designed as a provider-independent toolkit: the card catalog, pricing sources, auction references, image matching, and collection data are separate layers so one API can be replaced without rewriting the whole module.

## Phases implemented

### Phase 1 — Search, card lookup, pricing, bid ranges

- `Find-PokemonCard`
- `Get-PokemonCard`
- `Get-PokemonSet`
- `Get-PokemonCardPrice`
- `Get-PokemonBidRange`
- `pcard` alias for fast searching
- local response caching

The Pokemon TCG API is the primary catalog. TCGplayer price variants exposed by that API are flattened into PowerShell-friendly objects.

### Phase 2 — Additional price/listing providers

- optional PriceCharting provider for raw and graded guide prices
- optional eBay Browse provider for active listings
- eBay OAuth application-token handling
- provider-independent output from `Get-PokemonCardPrice`

Active eBay listings are intentionally not represented as sold comps.

### Phase 3 — Image-assisted identification

- `Identify-PokemonCard`
- optional local OCR with Python + Tesseract
- collector-number extraction (`233/091`, etc.)
- optional eBay `search_by_image`
- evidence-based candidate scoring
- canonical matches and reference images from Pokemon TCG API

### Phase 4 — Collection and set tracking

- `Import-PokemonCollection`
- `Add-PokemonCollectionCard`
- `Get-PokemonCollectionValue`
- `Get-PokemonSetChecklist`
- CSV / JSON imports plus optional `.xlsx` via `ImportExcel`
- owned/missing status, quantities, cost basis, market value, and missing-card pricing
- watch list with target prices and max bids
- append-only price history snapshots

## Requirements

- Windows PowerShell 5.1 or PowerShell 7.2+
- Internet access
- optional Pokemon TCG API key (recommended)
- optional PriceCharting paid API token
- optional eBay Developer Client ID and Client Secret
- optional Python 3 + Tesseract for local OCR

## Install from the repo

```powershell
git clone https://github.com/grans2631/PokemonSearch.git
cd PokemonSearch
Import-Module .\src\PokemonSearch\PokemonSearch.psd1 -Force
```

For a persistent local install:

```powershell
$destination = Join-Path $HOME 'Documents\WindowsPowerShell\Modules\PokemonSearch\0.1.1'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item .\src\PokemonSearch\* $destination -Recurse -Force
Import-Module PokemonSearch -Force
```

## Configure

Environment variables are best for automation:

```powershell
$env:POKEMONTCG_API_KEY = '...'
$env:PRICECHARTING_TOKEN = '...'
$env:EBAY_CLIENT_ID = '...'
$env:EBAY_CLIENT_SECRET = '...'
```

Or create a user-local configuration:

```powershell
Set-PokemonSearchConfig `
  -PokemonTcgApiKey '...' `
  -PriceChartingToken '...' `
  -EbayClientId '...' `
  -EbayClientSecret '...'
```

The local config lives under `~/.pokemonsearch/` and is not intended for GitHub.

## Fast card search

```powershell
pcard 'Mewtwo ex'

Find-PokemonCard -Name 'Gardevoir ex' -Number 233

Find-PokemonCard -SetName 'Paldean Fates' -Rarity 'Special Illustration Rare'
```

Useful columns:

```powershell
pcard 'Charizard ex' |
    Select-Object Name,SetName,Number,Rarity,Id |
    Format-Table -AutoSize
```

## Pricing

```powershell
Get-PokemonCardPrice -Id '<card-id>'
Get-PokemonCardPrice -Id '<card-id>' -Provider All
Get-PokemonCardPrice -Id '<card-id>' -Variant holofoil
```

`PokemonTCG` is the default provider. `All` attempts Pokemon TCG, PriceCharting, and eBay, but gracefully warns when optional providers have not been configured.

## Auction bid range

```powershell
Get-PokemonBidRange -Id '<card-id>'

Get-PokemonBidRange `
    -Id '<card-id>' `
    -Shipping 4.99 `
    -BuyerFeePercent 0 `
    -TargetDiscountPercent 20 `
    -UsePriceCharting
```

The output includes excellent/good/acceptable buy thresholds and a recommended maximum bid. Shipping, buyer fees, and a tax estimate can be deducted from the allowable all-in price.

## eBay active listings

```powershell
Get-PokemonEbayListing 'Mewtwo ex 162 Pokemon'
Get-PokemonEbayListing -CardId '<card-id>' -Limit 30
```

These are active listings, useful for supply and asking-price context. They are not sold comps.

## Identify a card from a photo

```powershell
Identify-PokemonCard -ImagePath .\card.jpg -IncludePricing
```

If optional services are unavailable:

```powershell
Identify-PokemonCard `
    -ImagePath .\card.jpg `
    -NameHint 'Gardevoir ex' `
    -NumberHint 233 `
    -SkipEbay `
    -IncludePricing
```

See [Image identification](docs/ImageIdentification.md).

## Collection

```powershell
Import-PokemonCollection -Path .\PokemonCards.csv
Get-PokemonCollectionValue
Get-PokemonCollectionValue -IncludeItems
```

Add a purchased card:

```powershell
Add-PokemonCollectionCard `
    -Id '<card-id>' `
    -Variant holofoil `
    -Condition 'Near Mint' `
    -PurchasePrice 32.00
```

Track an auction/watch target:

```powershell
Add-PokemonWatchCard -Id '<card-id>' -TargetPrice 35 -MaxBid 31
Get-PokemonWatchlist -Refresh -RecordHistory
```

Record and query historical prices:

```powershell
Update-PokemonPriceHistory -Id '<card-id>'
Get-PokemonPriceHistory -Id '<card-id>'
```

Find what is missing from a set:

```powershell
Get-PokemonSetChecklist -SetId '<set-id>' -MissingOnly -IncludePrices |
    Sort-Object @{ Expression = { if ($null -ne $_.Market) { [double]$_.Market } else { 0 } }; Descending = $true }
```

See [Collection and set tracking](docs/Collection.md).

## Provider notes

See [Providers](docs/Providers.md) for setup and API behavior.

## Security

Do not commit API keys, PriceCharting tokens, eBay secrets, or a real `config.json`. Secrets can be supplied by environment variable, and the repository `.gitignore` excludes common local secret files.

## Development

Run tests with Pester 5:

```powershell
Invoke-Pester -Path .\tests
```

GitHub Actions runs the test suite on Windows and includes a Windows PowerShell 5.1 module-import smoke test.

## Disclaimer

Prices are reference data, not guarantees of sale value. Card condition, language, printing, grading, fees, shipping, taxes, auction behavior, and market volatility can materially change realizable value and an appropriate bid.
