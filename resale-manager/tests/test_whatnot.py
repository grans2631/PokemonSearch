from datetime import date
import csv
from io import StringIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import InventoryEvent
from app.services.intake import create_inventory_item, create_purchase, find_or_create_card
from app.services.whatnot import (
    WHATNOT_HEADERS,
    add_show_item,
    create_show,
    export_show_csv,
    remove_show_item,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _queued_item(db: Session, *, name: str = "Meowth ex", number: str = "121/088"):
    purchase = create_purchase(
        db,
        purchase_date=date(2026, 8, 25),
        source_type="LOCAL",
        subtotal_cents=10000,
    )
    card = find_or_create_card(
        db,
        set_code="POR",
        set_name="Perfect Order",
        card_name=name,
        card_number=number,
        rarity="SIR",
    )
    return create_inventory_item(
        db,
        purchase=purchase,
        card=card,
        location_id=None,
        condition="NM",
        unit_cost_cents=4000,
        market_value_cents=7500,
        destination_status="WHATNOT_QUEUE",
    )


def test_show_numbers_and_add_item(db):
    item = _queued_item(db)
    first = create_show(db, name="Friday Singles")
    second = create_show(db, name="Saturday Singles")
    line = add_show_item(db, show=first, inventory=item, auction_start_cents=100)
    assert first.show_number == "WN000001"
    assert second.show_number == "WN000002"
    assert line.sequence_number == 1
    assert line.inventory_id == item.inventory_id


def test_non_whatnot_queue_item_is_rejected(db):
    purchase = create_purchase(db, purchase_date=date(2026, 8, 25), source_type="LOCAL", subtotal_cents=10000)
    card = find_or_create_card(db, set_code="POR", set_name="Perfect Order", card_name="Rosa", card_number="123/088", rarity="SIR")
    item = create_inventory_item(db, purchase=purchase, card=card, location_id=None, condition="NM", unit_cost_cents=3000, destination_status="READY")
    show = create_show(db, name="Friday Singles")
    with pytest.raises(ValueError, match="WHATNOT_QUEUE"):
        add_show_item(db, show=show, inventory=item)


def test_item_cannot_be_in_two_active_shows(db):
    item = _queued_item(db)
    first = create_show(db, name="Friday Singles")
    second = create_show(db, name="Saturday Singles")
    add_show_item(db, show=first, inventory=item)
    with pytest.raises(ValueError, match="another active Whatnot show"):
        add_show_item(db, show=second, inventory=item)


def test_export_matches_current_whatnot_columns(db):
    item = _queued_item(db)
    show = create_show(db, name="Friday Singles")
    add_show_item(db, show=show, inventory=item, auction_start_cents=100)
    show, text = export_show_csv(db, show.show_id)

    reader = csv.DictReader(StringIO(text))
    rows = list(reader)
    assert reader.fieldnames == WHATNOT_HEADERS
    assert len(rows) == 1
    row = rows[0]
    assert row["Category"] == "Trading Card Games"
    assert row["Sub Category"] == "Pokémon Cards"
    assert row["Type"] == "Auction"
    assert row["Price"] == "1.00"
    assert row["SKU"] == "POR-121-SIR-001"
    assert row["Cost Per Item"] == "40.00"
    assert show.status == "READY"
    assert show.export_generated_at is not None


def test_remove_records_audit_event(db):
    item = _queued_item(db)
    show = create_show(db, name="Friday Singles")
    line = add_show_item(db, show=show, inventory=item)
    remove_show_item(db, line)
    events = db.query(InventoryEvent).filter(InventoryEvent.inventory_id == item.inventory_id).all()
    assert any(event.event_type == "WHATNOT_SHOW_REMOVE" for event in events)
