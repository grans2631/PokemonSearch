# Pokemon Resale Manager

**Version:** v0.4.0 Whatnot Reconciliation

Pokemon Resale Manager is a self-hosted inventory and resale workflow application for Pokemon cards.

## Workflow

```text
PURCHASE -> INTAKE -> READY
                      |
                      +-> WHATNOT_QUEUE -> SHOW BUILDER -> WHATNOT CSV -> LIVE SHOW
                      |                                      |
                      |                                      +-> COMPLETED
                      |                                            |
                      |                                      SHOW REPORT CSV
                      |                                            |
                      |                                      RECONCILIATION
                      |                                        /       \
                      |                                     SOLD     UNSOLD
                      |                                      |          |
                      |                                   SALES     EBAY_QUEUE
                      |
                      +-> EBAY_QUEUE
```

## v0.4 capabilities

v0.4 includes the complete v0.2 intake workflow and v0.3 Whatnot Show Builder, then closes the post-show loop.

### Purchase and inventory intake

- Create purchases and calculate landed cost.
- Create/reuse card-set and card catalog records.
- Assign storage locations and immutable SKUs.
- Track condition, variant, grading, quantities, cost basis, market value, target price, and minimum price.
- Route inventory to READY, WHATNOT_QUEUE, EBAY_QUEUE, HOLD, or PERSONAL.

### Whatnot Show Builder

- Create sequential Whatnot shows.
- Add inventory from WHATNOT_QUEUE.
- Set run order, quantities, start prices, sale format, and title overrides.
- Export a current Whatnot-compatible show CSV using existing inventory data.

### Whatnot Show Report reconciliation

- Require the show to be marked `COMPLETED` before final reconciliation.
- Upload the final Whatnot Show Report CSV from the show page.
- Match sold rows to the exact inventory SKU exported by Resale Manager.
- Fall back to finding the known SKU inside report row content such as the exported description.
- Recognize multiple reasonable header aliases instead of depending on one fragile Whatnot report header name.
- Hard-stop the entire reconciliation if a sold row cannot be matched to the show's inventory.
- Create Whatnot `orders` and `sales` records.
- Capture sale price, quantity, Whatnot commission, payment-processing fees, and seller-paid shipping when present.
- Snapshot cost basis into the sale record so later inventory edits do not rewrite historical profit.
- Reduce quantity on hand and record inventory audit events.
- Mark fully sold inventory `SOLD`.
- Move unsold or partially remaining inventory to `EBAY_QUEUE`.
- Mark show items SOLD/UNSOLD and move the show to `RECONCILED`.
- SHA-256 fingerprint every imported report and prevent an identical file from creating duplicate sales.
- Block a different second report after final reconciliation in v0.4 to avoid accidentally changing inventory after it may have entered the eBay workflow.

### Sales ledger

The `/sales` page shows:

- Sale date
- Marketplace
- Whatnot show
- External order ID
- SKU and card
- Quantity
- Gross sale
- Cost basis
- Marketplace/processing/shipping costs
- Realized profit

It also provides aggregate gross sales, cost basis, fees, and realized profit.

## Whatnot report behavior

Whatnot currently documents its Show Report as containing item details, sale prices, fees, and totals. The exact report column names are intentionally handled through aliases in `app/services/whatnot_reconcile.py` so minor marketplace header changes do not require a database change.

The importer currently recognizes common variants of fields including:

```text
SKU
Order ID
Buyer
Quantity
Sale Price
Commission Fee
Payment Processing Fee
Total Fees
Seller Paid Shipping
Sold At
Order Status
Product Description
```

If a future Whatnot report uses different headings, only the reconciliation adapter should need adjustment.

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

GitHub Actions validates both the Resale Manager application and the preserved PokemonSearch PowerShell toolkit.

## Next milestone

v0.5 should focus on eBay OAuth and the eBay listing queue: turn inventory in `EBAY_QUEUE` into controlled eBay drafts/listings while retaining our database as the source of truth.
