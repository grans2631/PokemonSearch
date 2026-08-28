from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import AppSetting, Card, CardSet, InventoryImage, InventoryItem, Purchase
from app.services.ebay import EbayError
from app.services.ebay_v06 import EbayV06Service, TaxonomyValidation


class FakeEbayV06Service(EbayV06Service):
    def connection_status(self):
        return {"configured": True, "connected": True, "environment": "sandbox", "marketplace_id": "EBAY_US", "expires_at": None, "has_refresh_token": True}

    def validate_taxonomy(self, db, *, listing_id):
        listing, inventory = self._load_listing_inventory(db, listing_id)
        return TaxonomyValidation(
            category_id=self.get_setting(db, f"ebay.listing.{listing.listing_id}.category_id") or "183454",
            category_tree_id="0",
            required_aspects=["Game", "Card Name"],
            recommended_aspects=["Set"],
            missing_required_aspects=[],
            supplied_aspects=self._product_aspects(inventory),
        )

    def request(self, method, path, *, params=None, json_body=None):
        if path.endswith("/publish"):
            return {"listingId": "110000000001"}
        if path.endswith("/withdraw"):
            return {}
        return {}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def build_ready_draft(db: Session):
    purchase = Purchase(
        purchase_number="P000001", purchase_date=date(2026, 8, 28), source_type="LOCAL",
        subtotal_cents=2500, sales_tax_cents=0, shipping_cents=0, buyer_fees_cents=0,
        discount_cents=0, landed_cost_cents=2500, currency="USD", allocation_status="COMPLETE",
    )
    card_set = CardSet(name="Perfect Order", set_code="POR", language="EN")
    db.add_all([purchase, card_set])
    db.flush()
    card = Card(set_id=card_set.set_id, name="Meowth ex", card_number="121/088", rarity="SIR")
    db.add(card)
    db.flush()
    inventory = InventoryItem(
        sku="POR-121-SIR-001", card_id=card.card_id, purchase_id=purchase.purchase_id,
        inventory_type="SINGLE_CARD", tracking_mode="SERIALIZED", condition="NM", language="EN",
        is_graded=0, quantity_received=1, quantity_on_hand=1, unit_cost_cents=2500,
        target_price_cents=6999, status="EBAY_QUEUE",
    )
    db.add(inventory)
    db.flush()
    db.add(InventoryImage(
        inventory_id=inventory.inventory_id, image_order=1, is_primary=1,
        external_url="https://i.ebayimg.com/test.jpg", image_type="FRONT",
    ))
    for key, value in {
        "ebay.payment_policy_id": "PAY1",
        "ebay.fulfillment_policy_id": "FUL1",
        "ebay.return_policy_id": "RET1",
        "ebay.merchant_location_key": "LOC1",
        "ebay.default_category_id": "183454",
    }.items():
        db.add(AppSetting(setting_key=key, setting_value=value, data_type="string"))
    db.flush()
    service = FakeEbayV06Service()
    listing = service.create_local_draft(
        db, inventory=inventory, title=service.build_title(inventory), price_cents=6999, category_id="183454"
    )
    listing.external_offer_id = "OFFER1"
    listing.status = "PENDING"
    db.flush()
    return service, listing, inventory


def test_publish_requires_explicit_approval(db):
    service, listing, _ = build_ready_draft(db)
    with pytest.raises(EbayError, match="explicitly approved"):
        service.publish_offer_sandbox(db, listing_id=listing.listing_id)


def test_approve_publish_and_withdraw_sandbox(db):
    service, listing, inventory = build_ready_draft(db)
    service.approve_listing(db, listing_id=listing.listing_id)
    assert service.is_approved(db, listing.listing_id)

    external_id = service.publish_offer_sandbox(db, listing_id=listing.listing_id)
    assert external_id == "110000000001"
    assert listing.status == "ACTIVE"
    assert inventory.status == "EBAY_LISTED"

    service.withdraw_offer_sandbox(db, listing_id=listing.listing_id)
    assert listing.status == "PENDING"
    assert inventory.status == "EBAY_QUEUE"
    assert service.is_approved(db, listing.listing_id) is False


def test_taxonomy_preview_has_no_missing_required_aspects(db):
    service, listing, _ = build_ready_draft(db)
    preview = service.listing_preview(db, listing_id=listing.listing_id)
    assert preview["taxonomy"].missing_required_aspects == []
    assert preview["errors"] == []
