# Pokemon Resale Manager

**Version:** v0.6.0 eBay Sandbox Hardening + Windows Bootstrap

Pokemon Resale Manager is a self-hosted inventory and resale workflow application for Pokemon cards.

## Workflow

```text
PURCHASE -> INTAKE -> WHATNOT_QUEUE -> SHOW -> RECONCILE
                                         |          |
                                       SOLD      EBAY_QUEUE
                                                    |
                                              LOCAL DRAFT
                                                    |
                                          LOCAL CARD IMAGES
                                                    |
                                          eBay Picture Services
                                                    |
                                             OFFER DRAFT
                                                    |
                                         TAXONOMY VALIDATION
                                                    |
                                             HUMAN APPROVAL
                                                    |
                                         SANDBOX PUBLISH/WITHDRAW
```

## v0.6 capabilities

v0.6 retains the completed intake, Whatnot, reconciliation, sales, OAuth, and eBay Offer-draft workflows and adds the controls needed to prove the eBay path safely in Sandbox.

### Windows bootstrap + database

From this directory on a Windows machine:

```powershell
.\Setup-ResaleManager.ps1
```

The script automatically:

- locates Python 3.12+
- creates `.venv`
- installs requirements
- creates `.env` from `.env.example` if needed
- creates the `data` directory
- runs `alembic upgrade head`
- creates/updates `data/pokemon_resale_manager.db`
- verifies all 18 business tables plus the Alembic revision

Optional:

```powershell
.\Setup-ResaleManager.ps1 -Start
.\Setup-ResaleManager.ps1 -SeedDemo
```

Do not use `-SeedDemo` on a clean real inventory database unless demo records are wanted.

### Actual inventory images

The eBay Queue now accepts JPEG/PNG images of the physical card. Local files are stored under `data/images/<SKU>/` and tracked in `inventory_images`.

A local image can then be uploaded to eBay Picture Services using eBay's Media API. The EPS HTTPS URL returned by eBay is stored on the inventory image and supplied to the Inventory API listing payload.

### eBay Taxonomy validation

The Preview screen uses eBay Taxonomy metadata to:

- resolve the marketplace category tree
- show category suggestions from the generated title
- retrieve required/recommended aspects for the chosen category
- compare required aspect names against the aspects generated from our card metadata

Approval is blocked when required aspects are missing or Taxonomy validation fails.

### Explicit preview and approval

A synchronized Offer remains `PENDING`. The Preview page shows title, price, description, category, image state, Offer ID, Taxonomy aspects, and validation errors.

The user must explicitly acknowledge the review and approve the listing before publication. Re-syncing a draft clears approval.

### Sandbox publish / withdraw

When `EBAY_ENVIRONMENT=sandbox`, an approved Offer can call eBay `publishOffer`. The returned listing ID is stored locally, the listing becomes `ACTIVE`, and inventory becomes `EBAY_LISTED`.

An active Sandbox listing can be withdrawn with `withdrawOffer`; the Offer remains unpublished for reuse, the local listing returns to `PENDING`, inventory returns to `EBAY_QUEUE`, and approval is cleared.

**Production publication is intentionally blocked in v0.6.**

### Existing eBay v0.5 foundation

- OAuth User consent with access/refresh token handling
- Sandbox/Production credential separation
- seller privilege/program checks
- payment, fulfillment, and return policy retrieval
- Inventory API merchant locations
- local eBay drafts from `EBAY_QUEUE`
- graded/ungraded trading-card condition descriptors
- `createOrReplaceInventoryItem`
- create/update Inventory API Offer
- immutable Resale Manager SKU mapped to eBay SKU

See [`docs/ebay.md`](docs/ebay.md) for the complete Sandbox setup and test workflow.

## Previous completed workflows

- purchase and landed-cost tracking
- set/card catalog
- storage locations
- serialized/quantity inventory
- immutable SKU generation
- Whatnot Show Builder and CSV export
- Show Report reconciliation
- sold/unsold routing
- order, fee, cost-basis, and realized-profit capture
- Sales ledger
- inventory audit events

## Technology

- Python 3.12+
- FastAPI
- SQLAlchemy 2
- Alembic
- SQLite
- Jinja2
- httpx
- python-dotenv

## Manual setup alternative

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python scripts\verify_db.py
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

## Tests

```powershell
pytest
```

GitHub Actions validates both the Resale Manager application and the preserved PokemonSearch PowerShell toolkit.

## Next milestone

After an actual end-to-end Sandbox listing has been created and withdrawn successfully, the next milestone should add eBay order synchronization/fulfillment and a deliberately protected Production publication gate rather than simply enabling Production publishing by configuration alone.
