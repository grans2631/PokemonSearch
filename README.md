# Pokemon Resale Manager

This repository is evolving from the original **PokemonSearch** PowerShell toolkit into **Pokemon Resale Manager**, a self-hosted application for acquiring, cataloging, selling, and tracking Pokemon card inventory.

The resale application lives under [`resale-manager/`](resale-manager/). The original PowerShell toolkit remains under [`src/PokemonSearch/`](src/PokemonSearch/) and is intentionally preserved while useful catalog, pricing, eBay, and collection functionality is incorporated into the new application.

## Current release: v0.5

v0.5 adds the first controlled eBay integration layer to the completed intake and Whatnot-first workflow.

```text
PURCHASE -> INTAKE -> READY
                      |
                      +-> WHATNOT_QUEUE -> SHOW BUILDER -> LIVE SHOW
                                                       |
                                                SHOW REPORT IMPORT
                                                   /          \
                                                SOLD       UNSOLD
                                                 |             |
                                               SALES       EBAY_QUEUE
                                                               |
                                                       LOCAL EBAY DRAFT
                                                               |
                                                       EBAY OFFER DRAFT
                                                               |
                                                       NOT PUBLISHED
```

Current capabilities include:

- purchase and landed-cost tracking
- card/set catalog records
- storage locations
- serialized and quantity inventory
- immutable SKU generation
- cost-allocation controls
- Whatnot show creation and CSV export
- final Show Report reconciliation
- Whatnot order, fee, sale, and realized-profit capture
- automatic SOLD and EBAY_QUEUE routing
- Sales ledger and inventory audit events
- eBay Sandbox/Production OAuth User authorization
- eBay seller privilege, business-policy, and inventory-location retrieval
- controlled local eBay drafts from `EBAY_QUEUE`
- trading-card graded/ungraded condition mapping
- Inventory API item + Offer draft synchronization
- OAuth refresh-token handling and local secret storage

**v0.5 does not publish eBay offers.** The eBay integration intentionally stops after creating/updating the Inventory API Offer draft so the first Sandbox tests cannot accidentally make inventory live.

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
