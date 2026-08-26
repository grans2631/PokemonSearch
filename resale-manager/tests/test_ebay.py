from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Card, CardSet, InventoryItem, Listing, Purchase
from app.services.ebay import EbayError, EbayService


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def build_inventory(db: Session, *, graded: bool = False) -> InventoryItem:
    purchase = Purchase(
        purchase_number="P000001", purchase_date=date(2026, 8, 26), source_type="LOCAL",
        subtotal_cents=5000, sales_tax_cents=0, shipping_cents=0, buyer_fees_cents=0,
        discount_cents=0, landed_cost_cents=5000, currency="USD", allocation_status="COMPLETE",
    )
    card_set = CardSet(name="Perfect Order", set_code="POR", language="EN")
    db.add_all([purchase, card_set])
    db.flush()
    card = Card(set_id=card_set.set_id, name="Meowth ex", card_number="121/088", rarity="SIR")
    db.add(card)
    db.flush()
    item = InventoryItem(
        sku="POR-121-SIR-001", card_id=card.card_id, purchase_id=purchase.purchase_id,
        inventory_type="SINGLE_CARD", tracking_mode="SERIALIZED", condition="NM", language="EN",
        is_graded=1 if graded else 0,
        grading_company="PSA" if graded else None,
        grade="10" if graded else None,
        cert_number="12345678" if graded else None,
        quantity_received=1, quantity_on_hand=1, unit_cost_cents=2500,
        market_value_cents=6000, target_price_cents=6999, status="EBAY_QUEUE",
    )
    db.add(item)
    db.flush()
    return item


def test_ungraded_trading_card_condition_mapping(db):
    item = build_inventory(db)
    condition, descriptors = EbayService._condition_payload(item)
    assert condition == "USED_VERY_GOOD"
    assert descriptors == [{"name": "40001", "values": ["400010"]}]


def test_graded_trading_card_condition_mapping(db):
    item = build_inventory(db, graded=True)
    condition, descriptors = EbayService._condition_payload(item)
    assert condition == "LIKE_NEW"
    assert descriptors[0] == {"name": "27501", "values": ["275010"]}
    assert descriptors[1] == {"name": "27502", "values": ["275020"]}
    assert descriptors[2] == {"name": "27503", "additionalInfo": "12345678"}


def test_build_title_stays_within_ebay_limit(db):
    item = build_inventory(db, graded=True)
    title = EbayService.build_title(item)
    assert "Meowth ex" in title
    assert "PSA 10" in title
    assert len(title) <= 80


def test_create_local_ebay_draft_does_not_publish_or_move_inventory(db):
    item = build_inventory(db)
    service = EbayService()
    draft = service.create_local_draft(
        db, inventory=item, title=service.build_title(item), price_cents=6999, category_id="183454"
    )
    db.flush()
    assert draft.status == "DRAFT"
    assert draft.external_offer_id is None
    assert draft.external_listing_id is None
    assert item.status == "EBAY_QUEUE"
    assert db.query(Listing).count() == 1


def test_non_ebay_queue_inventory_cannot_be_drafted(db):
    item = build_inventory(db)
    item.status = "READY"
    with pytest.raises(EbayError, match="EBAY_QUEUE"):
        EbayService().create_local_draft(db, inventory=item, title="Test", price_cents=1000, category_id="183454")
