from datetime import date, datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Card, CardSet, IntegrationRun, InventoryEvent, InventoryItem, Order, Purchase, Sale, WhatnotShow, WhatnotShowItem
from app.services.whatnot_reconcile import import_show_report


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def build_show(db: Session):
    purchase = Purchase(
        purchase_number="P000001", purchase_date=date(2026, 8, 26), source_type="LOCAL",
        subtotal_cents=5000, sales_tax_cents=0, shipping_cents=0, buyer_fees_cents=0,
        discount_cents=0, landed_cost_cents=5000, currency="USD", allocation_status="COMPLETE",
    )
    card_set = CardSet(name="Perfect Order", set_code="POR", language="EN")
    db.add_all([purchase, card_set])
    db.flush()
    sold_card = Card(set_id=card_set.set_id, name="Meowth ex", card_number="121/088", rarity="SIR")
    unsold_card = Card(set_id=card_set.set_id, name="Rosa's Encouragement", card_number="123/088", rarity="SIR")
    db.add_all([sold_card, unsold_card])
    db.flush()
    sold_inventory = InventoryItem(
        sku="POR-121-SIR-001", card_id=sold_card.card_id, purchase_id=purchase.purchase_id,
        inventory_type="SINGLE_CARD", tracking_mode="SERIALIZED", condition="NM", language="EN",
        is_graded=0, quantity_received=1, quantity_on_hand=1, unit_cost_cents=2500,
        status="WHATNOT_QUEUE",
    )
    unsold_inventory = InventoryItem(
        sku="POR-123-SIR-001", card_id=unsold_card.card_id, purchase_id=purchase.purchase_id,
        inventory_type="SINGLE_CARD", tracking_mode="SERIALIZED", condition="NM", language="EN",
        is_graded=0, quantity_received=1, quantity_on_hand=1, unit_cost_cents=2500,
        status="WHATNOT_QUEUE",
    )
    db.add_all([sold_inventory, unsold_inventory])
    db.flush()
    show = WhatnotShow(
        show_number="WN000001", name="Test Show", status="COMPLETED",
        scheduled_at=datetime(2026, 8, 26, 1, 0, tzinfo=timezone.utc),
    )
    db.add(show)
    db.flush()
    sold_line = WhatnotShowItem(show_id=show.show_id, inventory_id=sold_inventory.inventory_id, sequence_number=1, quantity_planned=1, result_status="QUEUED")
    unsold_line = WhatnotShowItem(show_id=show.show_id, inventory_id=unsold_inventory.inventory_id, sequence_number=2, quantity_planned=1, result_status="QUEUED")
    db.add_all([sold_line, unsold_line])
    db.flush()
    return show, sold_inventory, unsold_inventory


def test_reconcile_sold_and_unsold(db):
    show, sold_inventory, unsold_inventory = build_show(db)
    report = b"SKU,Order ID,Buyer,Sale Price,Commission Fee,Payment Processing Fee,Quantity,Sold At,Status\nPOR-121-SIR-001,12345,buyer1,$40.00,$3.20,$1.20,1,2026-08-26 01:15:00,Complete\n"
    result = import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)
    db.commit()

    assert result.sale_records == 1
    assert result.sold_units == 1
    assert result.unsold_items == 1
    assert result.gross_cents == 4000
    assert result.fee_cents == 440
    assert result.realized_profit_cents == 1060
    assert sold_inventory.quantity_on_hand == 0
    assert sold_inventory.status == "SOLD"
    assert unsold_inventory.status == "EBAY_QUEUE"
    assert show.status == "RECONCILED"
    assert show.results_imported_at is not None
    assert db.scalar(select(Sale)) is not None
    assert db.scalar(select(Order)).external_order_id == "12345"
    assert db.scalar(select(IntegrationRun)).status == "COMPLETED"
    assert db.query(InventoryEvent).count() == 2


def test_same_report_is_idempotent(db):
    show, *_ = build_show(db)
    report = b"SKU,Sale Price,Fees\nPOR-121-SIR-001,40.00,4.40\n"
    first = import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)
    db.commit()
    second = import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)
    assert first.sale_records == 1
    assert second.duplicate is True
    assert db.query(Sale).count() == 1


def test_description_fallback_can_find_exported_sku(db):
    show, sold_inventory, _ = build_show(db)
    report = b"Product Description,Sold Price,Total Fees\nSKU: POR-121-SIR-001 | Set: Perfect Order,35.00,3.00\n"
    result = import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)
    assert result.sale_records == 1
    assert sold_inventory.status == "SOLD"


def test_unmatched_sold_row_stops_reconciliation(db):
    show, *_ = build_show(db)
    db.commit()
    show_id = show.show_id
    report = b"SKU,Sale Price\nUNKNOWN-SKU,20.00\n"
    with pytest.raises(ValueError, match="could not be matched"):
        import_show_report(db, show_id=show_id, filename="report.csv", content=report)
    db.rollback()
    assert db.get(WhatnotShow, show_id).status == "COMPLETED"
    assert db.query(Sale).count() == 0


def test_show_must_be_completed(db):
    show, *_ = build_show(db)
    show.status = "LIVE"
    report = b"SKU,Sale Price\nPOR-121-SIR-001,20.00\n"
    with pytest.raises(ValueError, match="COMPLETED"):
        import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)


def test_summary_total_row_is_ignored(db):
    show, *_ = build_show(db)
    report = (
        b"SKU,Title,Sale Price,Fees\n"
        b"POR-121-SIR-001,Meowth ex,40.00,4.00\n"
        b",Grand Total,40.00,4.00\n"
    )
    result = import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)
    assert result.sale_records == 1
    assert result.ignored_rows == 1


def test_multiple_items_can_accumulate_one_order_total(db):
    show, first, second = build_show(db)
    report = (
        b"SKU,Order ID,Sale Price,Quantity\n"
        b"POR-121-SIR-001,BUNDLE-1,40.00,1\n"
        b"POR-123-SIR-001,BUNDLE-1,20.00,1\n"
    )
    result = import_show_report(db, show_id=show.show_id, filename="report.csv", content=report)
    db.flush()
    order = db.scalar(select(Order).where(Order.external_order_id == "BUNDLE-1"))
    assert result.sale_records == 2
    assert order.order_total_cents == 6000
    assert first.status == "SOLD"
    assert second.status == "SOLD"
