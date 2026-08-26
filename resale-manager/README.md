# Pokemon Resale Manager

**Version:** v0.5.0 eBay OAuth + Draft Integration

Pokemon Resale Manager is a self-hosted inventory and resale workflow application for Pokemon cards.

## Workflow

```text
PURCHASE -> INTAKE -> READY
                      |
                      +-> WHATNOT_QUEUE -> SHOW BUILDER -> WHATNOT CSV -> LIVE SHOW
                      |                                            |
                      |                                      RECONCILIATION
                      |                                        /       \
                      |                                     SOLD     UNSOLD
                      |                                      |          |
                      |                                   SALES     EBAY_QUEUE
                      |                                                |
                      +------------------------------------------> LOCAL EBAY DRAFT
                                                                       |
                                                               EBAY OFFER DRAFT
                                                                       |
                                                               NOT PUBLISHED (v0.5)
```

## v0.5 capabilities

v0.5 retains the completed intake, Whatnot Show Builder, reconciliation, and sales-ledger workflows from prior milestones, then adds the first eBay integration layer.

### eBay OAuth

- Sandbox and Production environments are kept separate.
- OAuth User authorization-code flow with CSRF `state` validation.
- Requests `sell.account`, `sell.inventory`, and `sell.fulfillment` scopes.
- Exchanges the authorization code for User access/refresh tokens.
- Automatically refreshes expired access tokens.
- Stores OAuth tokens only in the local data directory, never in SQLite or Git.
- Supports disconnecting/removing the locally stored eBay token.
- `.env` is now loaded automatically at startup.

### Seller-account readiness

The `/ebay` page retrieves and displays:

- seller-registration / privilege information
- opted-in seller programs
- payment business policies
- fulfillment business policies
- return business policies
- Inventory API merchant locations

The user selects the three policy IDs and merchant location to use for Resale Manager listings. Those non-secret identifiers are stored in `app_settings`.

### eBay Queue

The `/ebay/queue` page shows inventory currently in `EBAY_QUEUE` and can:

- build an eBay title from card/set/grade metadata
- enforce eBay's 80-character title limit
- use target price or current market value as the draft-price starting point
- create/update a local `DRAFT` listing row
- preserve our immutable inventory SKU as the eBay SKU
- retain the inventory in `EBAY_QUEUE` while it is only a draft

### Trading-card condition mapping

For eBay's trading-card categories, v0.5 maps our inventory into eBay's Graded/Ungraded condition model:

- Ungraded -> `USED_VERY_GOOD` plus Card Condition descriptor
  - NM -> Near Mint or Better
  - LP -> Lightly Played
  - MP -> Moderately Played
  - HP/DMG -> Heavily Played/Poor
- Graded -> `LIKE_NEW` plus Professional Grader + Grade descriptors and certification number when present

Common grader IDs such as PSA, BGS, CGC, SGC, TAG, ACE and others are supported.

### Safe eBay draft synchronization

When **Sync Draft to eBay** is selected, v0.5:

1. validates inventory quantity, seller-policy defaults, category, merchant location, trading-card condition mapping, and actual-card image URLs;
2. calls eBay `createOrReplaceInventoryItem` using our SKU;
3. creates or updates an eBay Inventory API Offer;
4. stores the returned `offerId` in the local `listings` table;
5. records an inventory audit event;
6. leaves the local listing in `PENDING` state.

**v0.5 intentionally never calls `publishOffer`. It cannot make the offer live.**

At least one actual inventory photo with an external HTTPS URL is required before eBay synchronization. v0.5 intentionally does not substitute a catalog/reference image for the physical card.

See [`docs/ebay.md`](docs/ebay.md) for the full Sandbox/RuName setup process.

## Previous completed workflows

### Purchase and inventory intake

- Purchase/landed-cost tracking
- Card/set catalog reuse
- Storage locations
- Serialized or quantity inventory
- Immutable SKU generation
- Cost-basis allocation controls
- READY / WHATNOT_QUEUE / EBAY_QUEUE routing

### Whatnot

- Whatnot Show Builder
- Run-order/start-price controls
- Whatnot CSV export
- Show Report reconciliation
- Sold/unsold inventory routing
- Fee, cost-basis, and realized-profit capture
- Duplicate-file protection

### Sales ledger

The `/sales` page provides sale-level and aggregate gross sales, cost basis, fees/shipping, and realized profit.

## Technology

- Python 3.12+
- FastAPI
- SQLAlchemy 2
- Alembic
- SQLite
- Jinja2
- httpx
- python-dotenv

## Setup

From the `resale-manager` directory on Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

The SQLite database is created by default at `data/pokemon_resale_manager.db`.

## Tests

```powershell
pytest
```

GitHub Actions validates both the Resale Manager application and the preserved PokemonSearch PowerShell toolkit.

## Next milestone

Before enabling live eBay publication, the next milestone should harden the listing side: image upload/hosting, category/aspect metadata validation, explicit listing preview/approval, Sandbox publish/withdraw testing, and then controlled `publishOffer` support.
