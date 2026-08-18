# Collection and set tracking

PokemonSearch stores its normalized collection as JSON, by default at:

```text
~/.pokemonsearch/collection.json
```

You can import CSV, JSON, or Excel (`.xlsx`). Excel import uses the community `ImportExcel` PowerShell module if installed.

```powershell
Import-PokemonCollection -Path .\PokemonCards.xlsx
```

Common column names are normalized automatically, including `Name`, `Set`, `Number`, `Quantity`, `Condition`, `Variant`, and `Purchase Price`.

Add a canonical card directly from the API:

```powershell
Add-PokemonCollectionCard -Id 'sv4-151' -Variant holofoil -Quantity 1 -PurchasePrice 22.50
```

Value the collection using current Pokemon TCG/TCGplayer data:

```powershell
Get-PokemonCollectionValue
Get-PokemonCollectionValue -IncludeItems
```

Build a set checklist:

```powershell
Get-PokemonSetChecklist -SetId sv4 -IncludePrices
Get-PokemonSetChecklist -SetId sv4 -MissingOnly -IncludePrices
```

## Watch list and target prices

Add a target card:

```powershell
Add-PokemonWatchCard -Id '<card-id>' -TargetPrice 35 -MaxBid 31
```

If target price and max bid are omitted, PokemonSearch derives defaults from the current market and configured bid-discount rules.

Refresh the list against current prices:

```powershell
Get-PokemonWatchlist -Refresh
```

Refresh and also write a time-series snapshot:

```powershell
Get-PokemonWatchlist -Refresh -RecordHistory
```

## Price history

Record a snapshot:

```powershell
Update-PokemonPriceHistory -Id '<card-id>'
```

Read it later:

```powershell
Get-PokemonPriceHistory -Id '<card-id>'
```

History is stored as JSON Lines under `~/.pokemonsearch/price-history.jsonl` by default, making it append-friendly and easy to export for charts later.
