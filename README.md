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

The operating model intentionally uses Whatnot as the first-pass/live-sales channel for newly purchased cards and lots. Unsold inventory then moves to the long-tail eBay listing queue, avoiding the need to maintain simultaneous Whatnot BIN and eBay listings for the same serialized card.

## Resale Manager v0.1

The v0.1 foundation includes:

- Python 3.12 + FastAPI
- SQLAlchemy 2 ORM
- SQLite with foreign-key enforcement
- Alembic migrations
- 18-table inventory and commerce schema
- SKU generation
- Minimal dashboard, inventory, and purchase views
- Health and inventory JSON endpoints
- Demo seed command
- Initial tests
- Service boundaries for future eBay and Whatnot integrations

See [`resale-manager/README.md`](resale-manager/README.md) for setup and development instructions.

## Existing PokemonSearch toolkit

The original toolkit remains usable while the new application is developed. It currently contains card/set lookup, pricing providers, eBay active-listing lookup, collection tracking, price history, set checklists, and image-assisted identification.

```powershell
Import-Module .\src\PokemonSearch\PokemonSearch.psd1 -Force
pcard 'Mewtwo ex'
```

The original full command/setup reference is preserved at [`docs/PokemonSearch-Legacy.md`](docs/PokemonSearch-Legacy.md). Existing examples and supporting documentation remain in `examples/` and `docs/`.

## Development strategy

`main` remains the stable branch. New Resale Manager work is developed on feature branches and merged through pull requests after tests pass.

## Security

Do not commit API keys, OAuth tokens, marketplace secrets, buyer addresses, local configuration, or production SQLite databases.
