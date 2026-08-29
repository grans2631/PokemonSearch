from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import InventoryStatus, TrackingMode, InventoryType
from app.models import Card, CardSet, InventoryEvent, InventoryItem, Purchase, StorageLocation
from app.services.sku import build_bulk_sku, build_single_sku


VALID_QUEUE_STATUSES = {
    InventoryStatus.READY.value,
    InventoryStatus.WHATNOT_QUEUE.value,
    InventoryStatus.EBAY_QUEUE.value,
    InventoryStatus.HOLD.value,
    InventoryStatus.PERSONAL.value,
}


def money_to_cents(value: str | int | Decimal | None) -> int:
    """Convert a user-entered dollar amount to integer cents without float rounding."""
    if value is None or value == "":
        return 0
    try:
        amount = Decimal(str(value).strip().replace("$", "").replace(",", ""))
    except (InvalidOperation, AttributeError) as exc:
        raise ValueError(f"Invalid money amount: {value!r}") from exc
    if amount < 0:
        raise ValueError("Money amounts cannot be negative")
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_landed_cost_cents(*, subtotal_cents: int, sales_tax_cents: int = 0,
                                shipping_cents: int = 0, buyer_fees_cents: int = 0,
                                discount_cents: int = 0) -> int:
    gross = subtotal_cents + sales_tax_cents + shipping_cents + buyer_fees_cents
    if min(subtotal_cents, sales_tax_cents, shipping_cents, buyer_fees_cents, discount_cents) < 0:
        raise ValueError("Purchase amounts cannot be negative")
    if discount_cents > gross:
        raise ValueError("Discount cannot exceed purchase charges")
    return gross - discount_cents


def next_purchase_number(db: Session) -> str:
    existing = db.scalars(select(Purchase.purchase_number).where(Purchase.purchase_number.like("P%"))).all()
    highest = 0
    for value in existing:
        try:
            highest = max(highest, int(value[1:]))
        except (TypeError, ValueError):
            continue
    return f"P{highest + 1:06d}"


def create_purchase(db: Session, *, purchase_date: date, source_type: str,
                    source_name: str | None = None, external_order_id: str | None = None,
                    subtotal_cents: int = 0, sales_tax_cents: int = 0,
                    shipping_cents: int = 0, buyer_fees_cents: int = 0,
                    discount_cents: int = 0, notes: str | None = None) -> Purchase:
    landed = calculate_landed_cost_cents(
        subtotal_cents=subtotal_cents,
        sales_tax_cents=sales_tax_cents,
        shipping_cents=shipping_cents,
        buyer_fees_cents=buyer_fees_cents,
        discount_cents=discount_cents,
    )
    source_type = source_type.strip().upper()
    if not source_type:
        raise ValueError("Source type is required")
    purchase = Purchase(
        purchase_number=next_purchase_number(db),
        purchase_date=purchase_date,
        source_type=source_type,
        source_name=(source_name or "").strip() or None,
        external_order_id=(external_order_id or "").strip() or None,
        subtotal_cents=subtotal_cents,
        sales_tax_cents=sales_tax_cents,
        shipping_cents=shipping_cents,
        buyer_fees_cents=buyer_fees_cents,
        discount_cents=discount_cents,
        landed_cost_cents=landed,
        allocation_status="UNALLOCATED",
        notes=(notes or "").strip() or None,
    )
    db.add(purchase)
    db.flush()
    return purchase


def purchase_allocated_cents(db: Session, purchase_id: int) -> int:
    return int(db.scalar(
        select(func.coalesce(func.sum(InventoryItem.unit_cost_cents * InventoryItem.quantity_received), 0))
        .where(InventoryItem.purchase_id == purchase_id)
    ) or 0)


def refresh_purchase_allocation(db: Session, purchase: Purchase) -> tuple[int, int]:
    allocated = purchase_allocated_cents(db, purchase.purchase_id)
    if allocated == 0:
        status = "UNALLOCATED"
    elif allocated < purchase.landed_cost_cents:
        status = "PARTIAL"
    elif allocated == purchase.landed_cost_cents:
        status = "COMPLETE"
    else:
        raise ValueError("Allocated inventory cost exceeds purchase landed cost")
    purchase.allocation_status = status
    return allocated, purchase.landed_cost_cents - allocated


def find_or_create_card(db: Session, *, set_code: str, set_name: str, card_name: str,
                        card_number: str, rarity: str | None, language: str = "EN") -> Card:
    set_code = set_code.strip().upper()
    language = language.strip().upper() or "EN"
    if not set_code or not set_name.strip() or not card_name.strip() or not card_number.strip():
        raise ValueError("Set code, set name, card name, and card number are required")

    card_set = db.scalar(
        select(CardSet).where(CardSet.set_code == set_code, CardSet.language == language)
    )
    if card_set is None:
        card_set = CardSet(name=set_name.strip(), set_code=set_code, language=language)
        db.add(card_set)
        db.flush()

    card = db.scalar(
        select(Card).where(
            Card.set_id == card_set.set_id,
            Card.card_number == card_number.strip(),
            Card.name == card_name.strip(),
        )
    )
    if card is None:
        card = Card(
            set_id=card_set.set_id,
            name=card_name.strip(),
            card_number=card_number.strip(),
            rarity=(rarity or "").strip() or None,
            pokemon_name=card_name.strip(),
        )
        db.add(card)
        db.flush()
    elif rarity and not card.rarity:
        card.rarity = rarity.strip()
    return card


def create_storage_location(db: Session, *, location_code: str, name: str,
                            location_type: str = "SLOT", parent_location_id: int | None = None,
                            notes: str | None = None) -> StorageLocation:
    code = location_code.strip().upper()
    if not code or not name.strip():
        raise ValueError("Location code and name are required")
    if db.scalar(select(StorageLocation).where(StorageLocation.location_code == code)):
        raise ValueError(f"Storage location {code} already exists")
    location = StorageLocation(
        location_code=code,
        name=name.strip(),
        location_type=location_type.strip().upper() or "SLOT",
        parent_location_id=parent_location_id,
        notes=(notes or "").strip() or None,
        active=1,
    )
    db.add(location)
    db.flush()
    return location


def _next_unique_single_sku(db: Session, *, set_code: str, card_number: str, rarity: str,
                            language: str, grading_company: str | None, grade: str | None) -> str:
    for sequence in range(1, 1000):
        sku = build_single_sku(
            set_code=set_code,
            card_number=card_number,
            rarity=rarity or "CARD",
            sequence=sequence,
            language=language,
            grading_company=grading_company,
            grade=grade,
        )
        if db.scalar(select(InventoryItem.inventory_id).where(InventoryItem.sku == sku)) is None:
            return sku
    raise ValueError("No available SKU sequence remains for this card")


def _next_unique_bulk_sku(db: Session, *, set_code: str, card_number: str, variant: str,
                          language: str) -> str:
    for batch in range(1, 1000):
        sku = build_bulk_sku(
            set_code=set_code,
            card_number=card_number,
            variant=variant or "BULK",
            batch=batch,
            language=language,
        )
        if db.scalar(select(InventoryItem.inventory_id).where(InventoryItem.sku == sku)) is None:
            return sku
    raise ValueError("No available bulk SKU sequence remains for this card")


def create_inventory_item(db: Session, *, purchase: Purchase, card: Card,
                          location_id: int | None, condition: str | None,
                          language: str = "EN", finish: str | None = None,
                          variant_label: str | None = None, grading_company: str | None = None,
                          grade: str | None = None, cert_number: str | None = None,
                          quantity: int = 1, unit_cost_cents: int = 0,
                          market_value_cents: int | None = None,
                          target_price_cents: int | None = None,
                          minimum_price_cents: int | None = None,
                          destination_status: str = InventoryStatus.READY.value,
                          inventory_type: str = InventoryType.SINGLE_CARD.value,
                          tracking_mode: str = TrackingMode.SERIALIZED.value,
                          notes: str | None = None) -> InventoryItem:
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")
    if unit_cost_cents < 0:
        raise ValueError("Unit cost cannot be negative")
    destination_status = destination_status.strip().upper()
    if destination_status not in VALID_QUEUE_STATUSES:
        raise ValueError(f"Invalid intake destination: {destination_status}")

    allocated_before = purchase_allocated_cents(db, purchase.purchase_id)
    allocation = unit_cost_cents * quantity
    if allocated_before + allocation > purchase.landed_cost_cents:
        remaining = purchase.landed_cost_cents - allocated_before
        raise ValueError(
            f"Cost allocation exceeds purchase landed cost. Remaining allocatable amount is ${remaining / 100:.2f}."
        )

    language = language.strip().upper() or "EN"
    rarity = card.rarity or "CARD"
    card_set = card.card_set
    is_graded = bool((grading_company or "").strip() or (grade or "").strip())
    if is_graded and (not grading_company or not grade):
        raise ValueError("Grading company and grade are both required for graded inventory")

    if tracking_mode == TrackingMode.QUANTITY.value or inventory_type == InventoryType.BULK_LOT.value:
        sku = _next_unique_bulk_sku(
            db,
            set_code=card_set.set_code,
            card_number=card.card_number,
            variant=finish or variant_label or "BULK",
            language=language,
        )
    else:
        if quantity != 1:
            raise ValueError("Serialized inventory must have quantity 1")
        sku = _next_unique_single_sku(
            db,
            set_code=card_set.set_code,
            card_number=card.card_number,
            rarity=rarity,
            language=language,
            grading_company=(grading_company or "").strip().upper() or None,
            grade=(grade or "").strip() or None,
        )

    item = InventoryItem(
        sku=sku,
        card_id=card.card_id,
        purchase_id=purchase.purchase_id,
        location_id=location_id,
        inventory_type=inventory_type,
        tracking_mode=tracking_mode,
        condition=(condition or "").strip().upper() or None,
        language=language,
        finish=(finish or "").strip() or None,
        variant_label=(variant_label or "").strip() or None,
        is_graded=1 if is_graded else 0,
        grading_company=(grading_company or "").strip().upper() or None,
        grade=(grade or "").strip() or None,
        cert_number=(cert_number or "").strip() or None,
        quantity_received=quantity,
        quantity_on_hand=quantity,
        unit_cost_cents=unit_cost_cents,
        market_value_cents=market_value_cents,
        market_value_source="MANUAL" if market_value_cents is not None else None,
        target_price_cents=target_price_cents,
        minimum_price_cents=minimum_price_cents,
        status=destination_status,
        notes=(notes or "").strip() or None,
    )
    db.add(item)
    db.flush()
    db.add(InventoryEvent(
        inventory_id=item.inventory_id,
        event_type="INTAKE_CREATED",
        from_status=None,
        to_status=destination_status,
        quantity_delta=quantity,
        reference_type="PURCHASE",
        reference_id=purchase.purchase_id,
        message=f"Inventory created from {purchase.purchase_number}",
    ))
    refresh_purchase_allocation(db, purchase)
    return item


def transition_inventory(db: Session, item: InventoryItem, to_status: str, *, message: str | None = None) -> None:
    to_status = to_status.strip().upper()
    if to_status not in VALID_QUEUE_STATUSES:
        raise ValueError(f"Unsupported manual transition: {to_status}")
    old_status = item.status
    if old_status == to_status:
        return
    item.status = to_status
    db.add(InventoryEvent(
        inventory_id=item.inventory_id,
        event_type="STATUS_CHANGED",
        from_status=old_status,
        to_status=to_status,
        quantity_delta=0,
        message=message or "Manual inventory workflow transition",
    ))
