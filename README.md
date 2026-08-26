# Pokemon Resale Manager

This repository is evolving from the original **PokemonSearch** PowerShell toolkit into **Pokemon Resale Manager**: a self-hosted application for acquiring, cataloging, pricing, selling, and fulfilling Pokemon card inventory.

Development of the resale application currently lives under [`resale-manager/`](resale-manager/). The existing PowerShell PokemonSearch toolkit remains available under [`src/PokemonSearch/`](src/PokemonSearch/) and is being preserved while useful catalog, pricing, eBay, and collection functionality is progressively incorporated into the new application.

## Business workflow

```text
PURCHASE
   |
RECEIVED / INTAKE
   |
READY
   |-------------------|
   |                   |
WHATNOT_QUEUE       EBAY_QUEUE
   |                   |
WHATNOT SHOW        EBAY_LISTED
   |                   |
   |-- SOLD             SOLD
   |
   `-- UNSOLD --> EBAY_QUEUE
```

The operating model uses Whatnot as the first-pass/live-sales channel for newly purchased cards and lots. Unsold inventory then moves to the long-tail eBay listing queue, avoiding simultaneous Whatnot BIN and eBay listings for the same serialized card.

## Resale Manager v0.2

v0.2 is a usable acquisition and intake workflow. It adds purchase creation, landed-cost calculation, card/set catalog reuse, storage locations, inventory intake, automatic SKU generation, cost allocation controls, queue assignment, manual workflow transitions, dashboard queue counts, and local catalog search.

See [`resale-manager/README.md`](resale-manager/README.md) for setup and details.

## Existing PokemonSearch toolkit

The original toolkit remains usable and unchanged while the new application is developed. It contains card/set lookup, pricing providers, eBay active-listing lookup, collection tracking, price history, set checklists, and image-assisted identification.

```powershell
Import-Module .\src\PokemonSearch\PokemonSearch.psd1 -Force
pcard 'Mewtwo ex'
```

The original detailed toolkit documentation is preserved at [`docs/PokemonSearch-Legacy.md`](docs/PokemonSearch-Legacy.md).

## Development strategy

`main` remains the stable branch. Resale Manager work is developed on feature branches and merged through pull requests after validation.

## Security

Do not commit API keys, OAuth tokens, marketplace secrets, buyer addresses, local configuration, or production SQLite databases.
