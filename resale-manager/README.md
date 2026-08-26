# Pokemon Resale Manager

**Version:** v0.1.0 foundation

Pokemon Resale Manager is a small, self-hosted inventory and resale workflow application designed around a simple operating model:

1. Buy singles, lots, or collections.
2. Intake and assign cost basis to inventory.
3. Run selected fresh inventory on Whatnot first.
4. Move unsold Whatnot inventory into an eBay listing queue.
5. Track sales, fulfillment, fees, and realized profit.

The application is intentionally designed to avoid requiring Shopify, Vendoo, or another paid inventory hub.

## v0.1 scope

This repository contains the technical foundation rather than the complete marketplace automation layer.

- FastAPI application
- SQLAlchemy 2 ORM models
- SQLite database configuration with foreign-key enforcement
- Alembic migrations
- 18-table business schema
- Inventory lifecycle/status model
- Deterministic SKU generator
- Minimal dashboard, inventory, and purchases pages
- JSON health/inventory endpoints
- Seed/demo data command
- Basic tests
- Stubs for future eBay and Whatnot services

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

SQLite is deliberate for v0.1. The SQLAlchemy/Alembic layer keeps a future PostgreSQL move practical without redesigning the application.

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

Open:

```text
http://127.0.0.1:8000
```

API documentation:

```text
http://127.0.0.1:8000/docs
```

### Linux/macOS

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload
```

## Database

By default, the SQLite database is created at:

```text
data/pokemon_resale_manager.db
```

Schema documentation is in [`docs/schema.md`](docs/schema.md).

## SKU rules

SKUs identify the inventory we own and are immutable after creation.

Examples:

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

## What v0.2 should add

Recommended next milestone:

- Purchase intake forms
- Card/set catalog administration
- Inventory add/edit workflow
- Cost allocation for purchased lots
- Whatnot show builder
- Whatnot CSV export/import mapping
- eBay OAuth setup
- eBay Inventory API listing queue

## Security

Do not commit marketplace secrets, OAuth tokens, buyer addresses, or production database files. `.env` and local SQLite data are excluded by `.gitignore`.
