# Pokemon Resale Manager

**Version:** v0.3.0 Whatnot Show Builder

Pokemon Resale Manager is a self-hosted inventory and resale workflow application for Pokemon cards.

## Workflow

```text
PURCHASE -> INTAKE -> READY
                      |
                      +-> WHATNOT_QUEUE -> SHOW BUILDER -> WHATNOT CSV -> LIVE SHOW
                      |                                      |
                      |                                      +-> sold (v0.4 reconciliation)
                      |                                      +-> unsold -> EBAY_QUEUE
                      |
                      +-> EBAY_QUEUE
```

## v0.3 capabilities

v0.3 includes the complete v0.2 purchase and intake workflow plus the Whatnot Show Builder.

### Purchase and inventory intake

- Create purchases and calculate landed cost.
- Generate sequential purchase numbers.
- Create or reuse card-set and card catalog records.
- Assign storage locations.
- Track condition, language, finish, grading, quantities, cost basis, market value, target price, and minimum price.
- Generate immutable SKUs.
- Prevent purchase-cost over-allocation.
- Route inventory to READY, WHATNOT_QUEUE, EBAY_QUEUE, HOLD, or PERSONAL.

### Whatnot Show Builder

- Create sequential show numbers such as `WN000001`.
- Add cards directly from `WHATNOT_QUEUE`.
- Prevent one item from being assigned to multiple active Whatnot shows.
- Set run order, planned quantity, auction start, sale format, and optional title overrides.
- Remove cards from draft or ready shows.
- Track show state: DRAFT, READY, LIVE, COMPLETED, or CANCELLED.
- Record show add/remove activity in inventory audit events.
- Export the show to a Whatnot CSV without re-entering card data.
- Include SKU, cost basis, condition, quantity, price, and up to eight HTTPS image URLs.
- Record the CSV export time and row numbers for later result reconciliation.

The exporter is isolated in `app/services/whatnot.py` so marketplace template changes can be updated without changing the inventory schema.

## Whatnot CSV defaults

The v0.3 exporter follows Whatnot's current US/Australia/Netherlands non-Coins template shape documented in July 2026. Current defaults are:

```text
Category: Trading Card Games
Sub Category: Pokémon Cards
Shipping Profile: 0-1 oz
Hazmat: Not Hazmat
```

See `docs/whatnot.md` for the CSV field mapping.

## Technology

- Python 3.12+
- FastAPI
- SQLAlchemy 2
- Alembic
- SQLite
- Jinja2

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

GitHub Actions also validates the Resale Manager application and the preserved PokemonSearch PowerShell toolkit.

## Next milestone

v0.4: import a Whatnot Show Report, reconcile sold and unsold show inventory, create sales records, capture fees, move sold inventory to SOLD, and move unsold inventory to EBAY_QUEUE.
