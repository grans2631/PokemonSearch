from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import InventoryEvent
from app.services.intake import (
    calculate_landed_cost_cents,
    create_inventory_item,
    create_purchase,
    create_storage_location,
    find_or_create_card,
    money_to_cents,
    purchase_allocated_cents,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_money_parser_and_landed_cost():
    assert money_to_cents("$1,234.56") == 123456
    assert calculate_landed_cost_cents(subtotal_cents=10000, sales_tax_cents=700, shipping_cents=500, buyer_fees_cents=300, discount_cents=1000) == 10500


def test_purchase_intake_and_allocation(db):
    purchase = create_purchase(db, purchase_date=date(2026, 8, 25), source_type="whatnot", subtotal_cents=10000, shipping_cents=500)
    location = create_storage_location(db, location_code="B01-R01-S001", name="First slot")
    card = find_or_create_card(db, set_code="POR", set_name="Perfect Order", card_name="Meowth ex", card_number="121/088", rarity="SIR")
    item = create_inventory_item(db, purchase=purchase, card=card, location_id=location.location_id, condition="NM", unit_cost_cents=6000, market_value_cents=8000, destination_status="WHATNOT_QUEUE")
    db.flush()
    assert item.sku == "POR-121-SIR-001"
    assert item.status == "WHATNOT_QUEUE"
    assert purchase_allocated_cents(db, purchase.purchase_id) == 6000
    assert purchase.allocation_status == "PARTIAL"
    assert db.query(InventoryEvent).count() == 1


def test_duplicate_card_gets_next_sku(db):
    purchase = create_purchase(db, purchase_date=date(2026, 8, 25), source_type="LOCAL", subtotal_cents=10000)
    card = find_or_create_card(db, set_code="POR", set_name="Perfect Order", card_name="Meowth ex", card_number="121/088", rarity="SIR")
    first = create_inventory_item(db, purchase=purchase, card=card, location_id=None, condition="NM", unit_cost_cents=3000)
    second = create_inventory_item(db, purchase=purchase, card=card, location_id=None, condition="NM", unit_cost_cents=3000)
    assert first.sku == "POR-121-SIR-001"
    assert second.sku == "POR-121-SIR-002"


def test_overallocation_is_rejected(db):
    purchase = create_purchase(db, purchase_date=date(2026, 8, 25), source_type="LOCAL", subtotal_cents=5000)
    card = find_or_create_card(db, set_code="POR", set_name="Perfect Order", card_name="Meowth ex", card_number="121/088", rarity="SIR")
    with pytest.raises(ValueError, match="exceeds purchase landed cost"):
        create_inventory_item(db, purchase=purchase, card=card, location_id=None, condition="NM", unit_cost_cents=6000)
