# Whatnot CSV integration

Pokemon Resale Manager v0.3 exports show inventory using Whatnot's current US/Australia/Netherlands non-Coins CSV structure.

As of July 23, 2026, Whatnot documents CSV imports for both Inventory drafts and temporary listings inside a specific show. The current template includes:

- Category
- Sub Category
- Title
- Description
- Quantity
- Type
- Price
- Shipping Profile
- Offerable
- Hazmat
- Condition
- Cost Per Item
- SKU
- Image URL 1 through Image URL 8

Official help article:
https://help.whatnot.com/hc/en-us/articles/7440530071821-Bulk-import-products-from-a-CSV-file

## v0.3 defaults

The exporter currently uses:

- Category: `Trading Card Games`
- Sub Category: `Pokémon Cards`
- Shipping Profile: `0-1 oz`
- Hazmat: `Not Hazmat`
- Offerable: `FALSE`

Inventory condition abbreviations are mapped to readable Whatnot values where possible.

Marketplace-controlled CSV templates can change. Keep all Whatnot-specific translation in `app/services/whatnot.py` so a future template update does not affect the inventory schema.
