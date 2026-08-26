# Pokemon Resale Manager

**Version:** v0.2.0 intake workflow

Pokemon Resale Manager is a small, self-hosted inventory and resale workflow application designed around a simple operating model:

1. Buy singles, lots, or collections.
2. Intake and assign cost basis to inventory.
3. Run selected fresh inventory on Whatnot first.
4. Move unsold Whatnot inventory into an eBay listing queue.
5. Track sales, fulfillment, fees, and realized profit.

The application is intentionally designed to avoid requiring Shopify, Vendoo, or another paid inventory hub.

## v0.2 scope

v0.2 turns the v0.1 schema foundation into a usable acquisition and intake application.

- Create purchases with subtotal, tax, inbound shipping, buyer fees, discounts, source, and notes
- Server-side landed-cost calculation using integer cents
- Automatic purchase numbers (`P000001`, `P000002`, ...)
- Create or reuse local card/set catalog records during intake
- Create storage locations and assign inventory to them
- Add serialized singles or quantity/bulk inventory
- Generate unique immutable SKUs automatically
- Track condition, finish, language, grading, cert number, market value, target price, and minimum price
- Allocate purchase landed cost across inventory and prevent accidental over-allocation
- Automatically maintain `UNALLOCATED`, `PARTIAL`, and `COMPLETE` purchase allocation states
- Route new inventory directly to `READY`, `WHATNOT_QUEUE`, or `EBAY_QUEUE`
- Move inventory between manual workflow queues with an audit event
- Search the local card catalog through `/api/v1/cards/search`
- Dashboard queue counts and inventory filtering
- 13 automated tests plus an end-to-end fresh-database smoke test

The eBay and Whatnot marketplace integrations remain intentionally separated behind service boundaries for later milestones.

## Core workflow

```text
PURCHASE
   |
RECEIVED
   |
READY
   |-------------------|
   |                   |
WHATNOT_QUEUE       EBAY_QUEUE
   |                   |
WHATNOT SHOW        EBAY_LISTED
   |                   |
   |-- SOLD             SOLD
   |
   `-- UNSOLD --> EBAY_QUEUE
```

## Technology

- Python 3.12+
- FastAPI
- SQLAlchemy 2.0
- Alembic
- SQLite
- Jinja2 / simple server-rendered HTML

SQLite remains deliberate for the early releases. The SQLAlchemy/Alembic layer keeps a future PostgreSQL move practical without redesigning the application.

## Setup

### Windows PowerShell

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

Open `http://127.0.0.1:8000`. API documentation is at `http://127.0.0.1:8000/docs`.

## Database

By default, the SQLite database is created at `data/pokemon_resale_manager.db`.

Schema documentation is in [`docs/schema.md`](docs/schema.md).

## SKU rules

SKUs identify the inventory we own and are immutable after creation.

```text
POR-121-SIR-001
POR-121-SIR-PSA10-001
POR-JP-121-SIR-001
POR-042-RH-B001
```

See [`docs/architecture.md`](docs/architecture.md) for the design rules.

## Running tests

```bash
pytest
```

## Next milestone

Recommended v0.3 focus: **Whatnot Show Builder**. Inventory already queued as `WHATNOT_QUEUE` should be selectable into shows, ordered, assigned auction starts, and exported to Whatnot-compatible CSV without re-entering card data.

Later milestones can add Whatnot show-result reconciliation and then eBay OAuth/listing automation.

## Security

Do not commit marketplace secrets, OAuth tokens, buyer addresses, or production database files. `.env` and local SQLite data are excluded by `.gitignore`.
