from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models import Card, CardSet, InventoryEvent, InventoryItem, Purchase, StorageLocation
from app.services.sku import build_single_sku


def seed() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(Purchase).limit(1))
        if existing:
            print("Seed skipped: database already contains purchase data.")
            return

        card_set = CardSet(name="Demo Set", set_code="DMO", language="EN")
        card = Card(card_set=card_set, name="Demo Pikachu", card_number="001/100", rarity="IR", pokemon_name="Pikachu")
        purchase = Purchase(
            purchase_number="P000001",
            purchase_date=date.today(),
            source_type="OTHER",
            source_name="Demo Seed",
            subtotal_cents=2000,
            landed_cost_cents=2000,
            allocation_status="COMPLETE",
        )
        location = StorageLocation(location_code="B01-R01-S001", name="Demo Slot", location_type="SLOT")
        inventory = InventoryItem(
            sku=build_single_sku(set_code="DMO", card_number="001/100", rarity="IR", sequence=1),
            card=card,
            purchase=purchase,
            location=location,
            condition="NM",
            unit_cost_cents=2000,
            market_value_cents=3500,
            target_price_cents=3999,
            minimum_price_cents=3000,
            status="READY",
        )
        inventory.events.append(
            InventoryEvent(event_type="SEED_CREATED", from_status=None, to_status="READY", message="Demo inventory seed")
        )

        db.add_all([card_set, purchase, location, inventory])
        db.commit()
        print("Seed complete. Added demo purchase and inventory item.")


if __name__ == "__main__":
    seed()
