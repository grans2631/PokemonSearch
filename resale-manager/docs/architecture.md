# Architecture Decisions - v0.1

## Source of truth

Pokemon Resale Manager is the canonical inventory record. Marketplaces are sales channels, not inventory masters.

## Whatnot first, eBay second

New purchases and lot inventory can be queued for a Whatnot live show first. Items that sell are closed as sold. Items that do not sell move to the eBay queue. Persistent Whatnot BIN cross-listing is outside the initial workflow.

This avoids the need for real-time Whatnot/eBay cross-platform inventory cancellation in v0.1.

## Card catalog vs owned inventory

`cards` describes a card definition such as Meowth ex 121/088.

`inventory_items` describes an actual owned copy or quantity lot, including SKU, cost basis, condition, storage location, and lifecycle state.

## Purchase lineage

Every inventory item belongs to a purchase. A zero-cost purchase record can be used for previously owned inventory. Inventory from different purchases is never silently merged because doing so destroys lot-level cost-basis analysis.

## Money

Money is stored as integer cents. Never use floating-point values for financial records.

## SKU immutability

A SKU identifies inventory and never changes because of marketplace, price, status, or storage changes.

Preferred patterns:

- Raw single: `SET-NUMBER-RARITY-SEQUENCE`
- Graded: `SET-NUMBER-RARITY-GRADERGRADE-SEQUENCE`
- Non-English: `SET-LANGUAGE-NUMBER-RARITY-SEQUENCE`
- Quantity/bulk: `SET-NUMBER-VARIANT-B###`

## Inventory lifecycle

Supported v0.1 states:

- RECEIVED
- INTAKE
- READY
- WHATNOT_QUEUE
- EBAY_QUEUE
- EBAY_LISTED
- SOLD
- HOLD
- PERSONAL
- DAMAGED
- LOST
- ARCHIVED

All material inventory transitions should eventually generate an `inventory_events` row.

## Marketplace adapters

Marketplace-specific code belongs in `app/services/`. The database model does not depend on eBay or Whatnot implementation details beyond external IDs and marketplace names.

## Privacy

Do not persist buyer shipping addresses unless a future feature absolutely requires it. Marketplace order and fulfillment systems remain the source for personal shipping data.
