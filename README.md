# Pokemon Resale Manager

This repository is evolving from the original **PokemonSearch** PowerShell toolkit into **Pokemon Resale Manager**, a self-hosted application for acquiring, cataloging, selling, and tracking Pokemon card inventory.

The resale application lives under [`resale-manager/`](resale-manager/). The original PowerShell toolkit remains under [`src/PokemonSearch/`](src/PokemonSearch/) and is intentionally preserved.

## Current release: v0.6

v0.6 completes the first safe eBay Sandbox publication loop and adds a one-command Windows/database bootstrap.

```text
PURCHASE -> INTAKE -> WHATNOT -> RECONCILE -> EBAY_QUEUE
                                               |
                                         LOCAL CARD IMAGES
                                               |
                                         EBAY EPS IMAGES
                                               |
                                           OFFER DRAFT
                                               |
                                      TAXONOMY VALIDATION
                                               |
                                        HUMAN APPROVAL
                                               |
                                      SANDBOX PUBLISH
                                               |
                                      SANDBOX WITHDRAW
```

Current capabilities include:

- purchase and landed-cost tracking
- card/set catalog records
- storage locations
- serialized and quantity inventory
- immutable SKU generation
- Whatnot show creation and CSV export
- final Show Report reconciliation
- Sales ledger and realized-profit tracking
- eBay OAuth and seller policy/location retrieval
- local eBay drafts from `EBAY_QUEUE`
- actual card image storage and eBay Picture Services upload
- eBay Taxonomy category/aspect validation
- explicit listing preview/approval
- controlled Sandbox `publishOffer` and `withdrawOffer`
- Production publication blocked in v0.6
- Windows `Setup-ResaleManager.ps1` bootstrap
- automatic SQLite creation/migration at `resale-manager/data/pokemon_resale_manager.db`
- database verifier for all 18 business tables

See [`resale-manager/README.md`](resale-manager/README.md) for application setup and [`resale-manager/docs/ebay.md`](resale-manager/docs/ebay.md) for eBay Sandbox/OAuth setup.

## Existing PokemonSearch toolkit

The original toolkit remains usable and unchanged. It includes card/set lookup, pricing providers, eBay active-listing lookup, collection tracking, price history, set checklists, and image-assisted identification.

```powershell
Import-Module .\src\PokemonSearch\PokemonSearch.psd1 -Force
pcard 'Mewtwo ex'
```

The original detailed toolkit documentation is preserved at [`docs/PokemonSearch-Legacy.md`](docs/PokemonSearch-Legacy.md).

## Development strategy

`main` remains the stable branch. Resale Manager work is developed on feature branches and merged through pull requests after validation.
