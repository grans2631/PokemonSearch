# Database Schema - v0.1

The v0.1 schema contains 18 tables.

| Table | Purpose |
|---|---|
| `card_sets` | Pokemon set catalog metadata |
| `cards` | Card catalog metadata |
| `purchases` | Acquisition/lot/collection records and landed cost |
| `storage_locations` | Hierarchical physical storage locations |
| `inventory_items` | Owned physical inventory or quantity lots |
| `inventory_images` | Photos of owned inventory |
| `whatnot_shows` | Whatnot show batches |
| `whatnot_show_items` | Inventory assigned to shows and show results |
| `listings` | Marketplace listing records |
| `listing_items` | Inventory-to-listing join table; supports multi-card lots |
| `shipments` | Package/tracking/packing cost records |
| `orders` | Marketplace order containers |
| `sales` | Item-level financial sale records |
| `inventory_events` | Inventory audit trail |
| `price_snapshots` | Historical market pricing |
| `integration_runs` | CSV/API import/export job history and idempotency support |
| `business_expenses` | Business expenses not always attributable to one card |
| `app_settings` | Non-secret application settings |

## Important constraints

- `inventory_items.sku` is unique.
- `purchases.purchase_number` is unique.
- `storage_locations.location_code` is unique.
- `whatnot_shows.show_number` is unique.
- The same inventory item cannot be added twice to the same Whatnot show.
- `listing_items` prevents duplicate inventory/listing pairs.
- External order IDs are unique per marketplace.
- Money is integer cents.
- Quantities and monetary cost fields have non-negative checks where appropriate.

## Primary relationships

```text
card_sets --> cards --> inventory_items <-- purchases
                         |
                         +--> inventory_images
                         +--> inventory_events
                         +--> whatnot_show_items --> whatnot_shows
                         +--> listing_items --> listings
                         +--> sales --> orders --> shipments

cards --> price_snapshots
```
