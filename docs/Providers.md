# Data providers

## Pokemon TCG API

Primary card catalog and default raw-card pricing source. PokemonSearch uses the v2 API for card/set metadata, card images, and the TCGplayer price object exposed on card records.

Configure with either:

```powershell
$env:POKEMONTCG_API_KEY = '...'
```

or:

```powershell
Set-PokemonSearchConfig -PokemonTcgApiKey '...'
```

An API key is recommended for higher rate limits.

## PriceCharting

Optional paid provider used for another raw-price reference and graded-price estimates. PriceCharting prices are returned as integer pennies by its API; PokemonSearch converts them to dollars.

```powershell
$env:PRICECHARTING_TOKEN = '...'
```

## eBay Browse API

Optional provider for current active listings and image-based listing search. It requires an eBay developer application Client ID and Client Secret.

```powershell
$env:EBAY_CLIENT_ID = '...'
$env:EBAY_CLIENT_SECRET = '...'
```

PokemonSearch obtains an application access token using the client-credentials flow and caches the token in memory until shortly before expiration.

**Important:** Browse API results are active listings. PokemonSearch does not label them as sold comps and does not use active asking prices as the default market value for bid recommendations.

## Secret handling

Environment variables are preferred for automation. `Set-PokemonSearchConfig` can store credentials in the current user's `~/.pokemonsearch/config.json`; never commit that file or a real credential file to GitHub.
