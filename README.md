# Pokemon Resale Manager

This repository is evolving from the original **PokemonSearch** PowerShell toolkit into **Pokemon Resale Manager**, a self-hosted application for acquiring, cataloging, selling, and tracking Pokemon card inventory.

The resale application lives under [`resale-manager/`](resale-manager/). The original PowerShell toolkit remains under [`src/PokemonSearch/`](src/PokemonSearch/) and is intentionally preserved while useful catalog, pricing, eBay, and collection functionality is incorporated into the new application.

## Current release: v0.4

v0.4 closes the Whatnot loop by importing the final Show Report and reconciling each show's inventory into sales and the eBay queue.

```text
PURCHASE -> INTAKE -> READY
                      |
                      +-> WHATNOT_QUEUE -> SHOW BUILDER -> WHATNOT CSV -> LIVE SHOW
                                                              |
                                                           COMPLETED
                                                              |
                                                      SHOW REPORT IMPORT
                                                         /          \
                                                      SOLD       UNSOLD
                                                       |             |
                                                     SALES       EBAY_QUEUE
                      |
                      +-> EBAY_QUEUE
```

Current capabilities include:

- purchase and landed-cost tracking
- card/set catalog records
- storage locations
- serialized and quantity inventory
- immutable SKU generation
- cost-allocation controls
- Whatnot and eBay workflow queues
- Whatnot show creation and run ordering
- Whatnot-compatible CSV export
- final Show Report import and SKU reconciliation
- Whatnot order, fee, sale, and realized-profit capture
- automatic SOLD and EBAY_QUEUE routing
- duplicate report protection
- Sales ledger and inventory audit events

See [`resale-manager/README.md`](resale-manager/README.md) for setup and workflow details.

## Existing PokemonSearch toolkit

The original toolkit remains usable and unchanged. It includes card/set lookup, pricing providers, eBay active-listing lookup, collection tracking, price history, set checklists, and image-assisted identification.

```powershell
Import-Module .\src\PokemonSearch\PokemonSearch.psd1 -Force
pcard 'Mewtwo ex'
```

The original detailed toolkit documentation is preserved at [`docs/PokemonSearch-Legacy.md`](docs/PokemonSearch-Legacy.md).

## Development strategy

`main` remains the stable branch. Resale Manager work is developed on feature branches and merged through pull requests after validation.
