# eBay integration (v0.5)

v0.5 adds eBay OAuth, seller-account readiness checks, business-policy/location selection, local eBay drafts, and synchronization of an Inventory API item + Offer draft.

**v0.5 never calls `publishOffer`. Nothing becomes a live eBay listing from this release.**

## 1. Start in eBay Sandbox

Create or use an eBay Developer Program application and begin with the Sandbox keyset. You need:

- Client ID (App ID)
- Client Secret (Cert ID)
- OAuth Redirect URL name (RuName)

The application requests these User OAuth scopes:

```text
https://api.ebay.com/oauth/api_scope/sell.account
https://api.ebay.com/oauth/api_scope/sell.inventory
https://api.ebay.com/oauth/api_scope/sell.fulfillment
```

The fulfillment scope is included now so a later order-sync milestone does not immediately require another consent flow.

## 2. Configure the RuName

In the eBay Developer Portal, open the User Tokens settings for the same Sandbox or Production keyset and create/configure an OAuth Redirect URL name (RuName).

The RuName's **Auth Accepted URL** must point to the running application's callback endpoint:

```text
https://YOUR-HTTPS-HOST/ebay/oauth/callback
```

eBay requires the consent flow to use the RuName value as the OAuth `redirect_uri`; the RuName itself contains the actual Accepted/Declined URLs.

For a local-only installation, expose the application through an HTTPS-capable reverse proxy/tunnel or another HTTPS endpoint that the browser can reach during the consent redirect. Keep Sandbox and Production RuNames/keysets separate.

## 3. Configure `.env`

Copy `.env.example` to `.env` and fill in:

```text
EBAY_ENVIRONMENT=sandbox
EBAY_CLIENT_ID=...
EBAY_CLIENT_SECRET=...
EBAY_RUNAME=...
EBAY_MARKETPLACE_ID=EBAY_US
EBAY_LOCALE=en-US
EBAY_DEFAULT_CATEGORY_ID=183454
```

The application now loads `.env` automatically at startup.

`183454` is the default leaf category used by v0.5 for Collectible Card Games / Individual Cards. A different category can be entered for an individual local draft.

## 4. Connect the seller account

Start the app and open:

```text
/ebay
```

Choose **Connect eBay Seller Account**. After consent, eBay returns the authorization code to `/ebay/oauth/callback`; the app exchanges it for a User access token and refresh token.

Tokens are stored locally under the configured data directory in:

```text
data/ebay_oauth.json
```

The file is excluded from Git and written with restrictive file permissions where the OS supports them. It is not stored in the SQLite database.

## 5. Seller readiness

After connection, the eBay page retrieves:

- seller-registration/privilege status
- opted-in seller programs
- payment policies
- fulfillment policies
- return policies
- Inventory API locations

Inventory API offers require all three business-policy IDs and a merchant inventory location. The seller account must also be opted into eBay Selling Policy Management / Business Policies.

Select one payment, fulfillment, and return policy plus an inventory location on the eBay settings page. These IDs are non-secret and are stored in `app_settings`.

## 6. eBay queue workflow

Open:

```text
/ebay/queue
```

Only inventory in `EBAY_QUEUE` with quantity on hand is shown.

For each card:

1. Review the generated title (max 80 characters).
2. Review/set the fixed-price amount.
3. Review/set the eBay category ID.
4. Create the local draft.
5. When prerequisites are satisfied, choose **Sync Draft to eBay**.

The sync operation:

1. Calls `createOrReplaceInventoryItem` for our immutable SKU.
2. Creates or updates an eBay Offer.
3. Stores the returned `offerId` in the local `listings` row.
4. Leaves the listing in local `PENDING` state.
5. Does **not** call `publishOffer`.

## 7. Trading-card condition mapping

For the eBay trading-card categories, v0.5 follows eBay's Graded/Ungraded condition model.

Ungraded inventory uses the Inventory API condition `USED_VERY_GOOD` with the trading-card condition descriptor:

- NM -> Near Mint or Better
- LP -> Lightly Played
- MP -> Moderately Played
- HP / DMG -> Heavily Played / Poor

Graded inventory uses `LIKE_NEW` plus eBay's Professional Grader and Grade condition descriptors. Common graders including PSA, BGS, CGC, SGC, TAG, ACE, and others are mapped. Certification number is passed when available.

## 8. Images

Before an Inventory API draft can sync, v0.5 requires at least one **actual inventory image** with an external HTTPS URL. Catalog/reference artwork is intentionally not substituted for a photograph of the physical card.

Image upload/hosting automation is not part of v0.5; that should be addressed before live publishing is enabled.

## 9. Production cutover

Do not change `EBAY_ENVIRONMENT` to `production` until Sandbox OAuth, seller-account retrieval, policy selection, inventory-item creation, and offer-draft creation have all been verified.

Production uses a separate eBay Client ID, Client Secret, and RuName from Sandbox.
