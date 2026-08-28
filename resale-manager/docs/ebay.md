# eBay integration (v0.6)

v0.6 extends the v0.5 OAuth/Offer-draft integration with actual inventory image handling, eBay Picture Services upload, Taxonomy validation, explicit human approval, and controlled Sandbox publish/withdraw testing.

**Production publication remains blocked in v0.6.**

## 1. Start in eBay Sandbox

Use an eBay Developer Program Sandbox keyset. Configure these values in `.env`:

```text
EBAY_ENVIRONMENT=sandbox
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
EBAY_RUNAME=...
EBAY_MARKETPLACE_ID=EBAY_US
EBAY_LOCALE=en-US
EBAY_DEFAULT_CATEGORY_ID=183454
```

The User OAuth consent flow requests:

```text
https://api.ebay.com/oauth/api_scope/sell.account
https://api.ebay.com/oauth/api_scope/sell.inventory
https://api.ebay.com/oauth/api_scope/sell.fulfillment
```

The application separately obtains an Application access token with the base eBay OAuth scope for Taxonomy/metadata and Media API operations.

## 2. Configure the RuName

In eBay Developer Portal, configure the Sandbox OAuth Redirect URL name (RuName). Its Accepted URL must point to:

```text
https://YOUR-HTTPS-HOST/ebay/oauth/callback
```

The `EBAY_RUNAME` value is the Redirect URL name, not the literal callback URL.

## 3. Connect the seller account

Open `/ebay` and choose **Connect eBay Seller Account**. Tokens are stored only in the local data directory:

```text
data/ebay_oauth.json
```

They are excluded from Git and are not stored in SQLite.

## 4. Select seller defaults

The eBay page retrieves seller readiness, programs, payment policy, fulfillment policy, return policy, and Inventory API locations. Select all three business policies plus a merchant location and default category.

## 5. Add actual card images

On `/ebay/queue`, upload JPEG or PNG photos of the physical inventory item. Files are stored under:

```text
data/images/<SKU>/
```

They are tracked in `inventory_images` with a SHA-256 hash and local path.

Choose **Upload to eBay** to send a local image to the eBay Media API `createImageFromFile` endpoint. The runtime uses the `apim.ebay.com` / `apim.sandbox.ebay.com` Media host. eBay's returned EPS HTTPS image URL is then stored in `inventory_images.external_url` and used by the Inventory API product payload.

## 6. Create and synchronize the draft

Create the local draft from `EBAY_QUEUE`, then choose **Sync Offer Draft**. This:

1. validates quantity, selected policies/location/category, trading-card condition mapping, and EPS image availability;
2. calls `createOrReplaceInventoryItem` using our immutable SKU;
3. creates or updates the eBay Offer;
4. stores the returned `offerId`;
5. leaves the local listing `PENDING` and unpublished.

## 7. Taxonomy validation

The listing Preview screen calls the Taxonomy API to:

- resolve the marketplace category tree;
- retrieve eBay category suggestions from the listing title;
- retrieve item aspects for the selected category;
- identify required and recommended aspects;
- compare required aspect names against the aspects generated from our card metadata.

The application currently supplies aspects such as Game, Card Name, Card Number, Set, Rarity, and Language when that metadata is available.

If a required eBay aspect is missing, approval is blocked.

## 8. Human approval gate

Open **Preview / Approve** for the draft. Review:

- physical-card images
- title
- price
- category
- description
- offer ID
- supplied aspects
- required/recommended Taxonomy aspects
- validation errors

A synchronized `PENDING` offer cannot be published until the user explicitly checks the review acknowledgement and approves it.

Any later draft re-sync clears that approval and requires another review.

## 9. Sandbox publish

If `EBAY_ENVIRONMENT=sandbox`, an approved `PENDING` offer can call:

```text
POST /sell/inventory/v1/offer/{offerId}/publish
```

The returned eBay `listingId` is stored locally, listing state becomes `ACTIVE`, and inventory state becomes `EBAY_LISTED`.

If the application is configured for Production, v0.6 rejects the publish operation before making the API request.

## 10. Sandbox withdraw

An active Sandbox listing can be withdrawn with:

```text
POST /sell/inventory/v1/offer/{offerId}/withdraw
```

The eBay Offer is retained in unpublished state, the local listing returns to `PENDING`, inventory returns to `EBAY_QUEUE`, and approval is cleared.

## 11. Windows setup and database creation

From the `resale-manager` directory, run:

```powershell
.\Setup-ResaleManager.ps1
```

The script:

- locates Python 3.12+
- creates `.venv`
- installs dependencies
- creates `.env` if missing
- applies Alembic migrations
- creates/updates `data/pokemon_resale_manager.db`
- verifies all 18 business tables plus `alembic_version`

Optional switches:

```powershell
.\Setup-ResaleManager.ps1 -SeedDemo
.\Setup-ResaleManager.ps1 -Start
```

`-SeedDemo` should not be used for a clean production inventory database unless demo records are actually wanted.

## Production cutover

Production publishing is intentionally not implemented in v0.6. The Sandbox workflow should be proven end-to-end first: OAuth -> policies/location -> local image -> EPS image -> Inventory Item -> Offer -> Taxonomy validation -> approval -> publish -> withdraw.
