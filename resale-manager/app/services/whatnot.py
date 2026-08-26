from __future__ import annotations

import csv
import re
from io import StringIO
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import InventoryStatus, WhatnotResultStatus, WhatnotShowStatus
from app.models import Card, InventoryEvent, InventoryItem, WhatnotShow, WhatnotShowItem
from app.models.base import utcnow


WHATNOT_HEADERS = [
    "Category", "Sub Category", "Title", "Description", "Quantity", "Type", "Price",
    "Shipping Profile", "Offerable", "Hazmat", "Condition", "Cost Per Item", "SKU",
    "Image URL 1", "Image URL 2", "Image URL 3", "Image URL 4",
    "Image URL 5", "Image URL 6", "Image URL 7", "Image URL 8",
]

DEFAULT_CATEGORY = "Trading Card Games"
DEFAULT_SUB_CATEGORY = "Pokémon Cards"
DEFAULT_SHIPPING_PROFILE = "0-1 oz"

CONDITION_MAP = {
    "NM": "Near Mint",
    "LP": "Lightly Played",
    "MP": "Moderately Played",
    "HP": "Heavily Played",
    "DMG": "Damaged",
}

TYPE_MAP = {
    "AUCTION": "Auction",
    "BUY_IT_NOW": "Buy It Now",
    "GIVEAWAY": "Giveaway",
}


def _money(cents: int | None) -> str:
    return f"{(cents or 0) / 100:.2f}"


def next_show_number(db: Session) -> str:
    values = db.scalars(
        select(WhatnotShow.show_number).order_by(WhatnotShow.show_id.desc()).limit(250)
    ).all()
    highest = 0
    for value in values:
        match = re.fullmatch(r"WN(\d+)", value or "", re.IGNORECASE)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"WN{highest + 1:06d}"


def create_show(
    db: Session,
    *,
    name: str,
    scheduled_at: datetime | None = None,
    theme: str | None = None,
    notes: str | None = None,
) -> WhatnotShow:
    name = name.strip()
    if not name:
        raise ValueError("Show name is required")
    show = WhatnotShow(
        show_number=next_show_number(db),
        name=name,
        scheduled_at=scheduled_at,
        status=WhatnotShowStatus.DRAFT.value,
        theme=(theme or "").strip() or None,
        notes=(notes or "").strip() or None,
    )
    db.add(show)
    db.flush()
    return show


def get_show(db: Session, show_id: int, *, with_items: bool = False) -> WhatnotShow:
    stmt = select(WhatnotShow).where(WhatnotShow.show_id == show_id)
    if with_items:
        stmt = stmt.options(
            joinedload(WhatnotShow.items)
            .joinedload(WhatnotShowItem.inventory_item)
            .joinedload(InventoryItem.card)
            .joinedload(Card.card_set),
            joinedload(WhatnotShow.items)
            .joinedload(WhatnotShowItem.inventory_item)
            .joinedload(InventoryItem.images),
        )
        show = db.execute(stmt).unique().scalar_one_or_none()
    else:
        show = db.scalar(stmt)
    if show is None:
        raise ValueError("Whatnot show not found")
    return show


def eligible_inventory(db: Session) -> list[InventoryItem]:
    return db.scalars(
        select(InventoryItem)
        .where(
            InventoryItem.status == InventoryStatus.WHATNOT_QUEUE.value,
            InventoryItem.quantity_on_hand > 0,
        )
        .options(
            joinedload(InventoryItem.card).joinedload(Card.card_set),
            joinedload(InventoryItem.location),
        )
        .order_by(InventoryItem.inventory_id)
    ).all()


def _ensure_editable(show: WhatnotShow) -> None:
    if show.status not in {WhatnotShowStatus.DRAFT.value, WhatnotShowStatus.READY.value}:
        raise ValueError(f"Show cannot be edited while status is {show.status}")


def _next_sequence(db: Session, show_id: int) -> int:
    value = db.scalar(
        select(func.max(WhatnotShowItem.sequence_number)).where(WhatnotShowItem.show_id == show_id)
    )
    return (value or 0) + 1


def add_show_item(
    db: Session,
    *,
    show: WhatnotShow,
    inventory: InventoryItem,
    quantity: int = 1,
    auction_start_cents: int = 100,
    title_override: str | None = None,
    sale_format: str = "AUCTION",
) -> WhatnotShowItem:
    _ensure_editable(show)
    if inventory.status != InventoryStatus.WHATNOT_QUEUE.value:
        raise ValueError(f"{inventory.sku} is not in WHATNOT_QUEUE")
    if quantity < 1 or quantity > inventory.quantity_on_hand:
        raise ValueError(f"Invalid quantity for {inventory.sku}")
    sale_format = sale_format.upper().strip()
    if sale_format not in TYPE_MAP:
        raise ValueError("Unsupported Whatnot sale format")
    if auction_start_cents < 0:
        raise ValueError("Auction start cannot be negative")

    existing = db.scalar(
        select(WhatnotShowItem).where(
            WhatnotShowItem.show_id == show.show_id,
            WhatnotShowItem.inventory_id == inventory.inventory_id,
        )
    )
    if existing:
        raise ValueError(f"{inventory.sku} is already in this show")

    other_active = db.scalar(
        select(WhatnotShowItem)
        .join(WhatnotShow)
        .where(
            WhatnotShowItem.inventory_id == inventory.inventory_id,
            WhatnotShowItem.show_id != show.show_id,
            WhatnotShowItem.result_status.in_([
                WhatnotResultStatus.QUEUED.value,
                WhatnotResultStatus.RUN.value,
            ]),
            WhatnotShow.status.in_([
                WhatnotShowStatus.DRAFT.value,
                WhatnotShowStatus.READY.value,
                WhatnotShowStatus.LIVE.value,
            ]),
        )
        .limit(1)
    )
    if other_active:
        raise ValueError(f"{inventory.sku} is already assigned to another active Whatnot show")

    show_item = WhatnotShowItem(
        show_id=show.show_id,
        inventory_id=inventory.inventory_id,
        sequence_number=_next_sequence(db, show.show_id),
        quantity_planned=quantity,
        title_override=(title_override or "").strip() or None,
        auction_start_cents=auction_start_cents,
        sale_format=sale_format,
        result_status=WhatnotResultStatus.QUEUED.value,
    )
    db.add(show_item)
    db.flush()
    db.add(InventoryEvent(
        inventory_id=inventory.inventory_id,
        event_type="WHATNOT_SHOW_ADD",
        from_status=inventory.status,
        to_status=inventory.status,
        quantity_delta=0,
        marketplace="WHATNOT",
        reference_type="WHATNOT_SHOW",
        reference_id=show.show_id,
        message=f"Added to {show.show_number}",
    ))
    db.flush()
    return show_item


def update_show_item(
    db: Session,
    *,
    show_item: WhatnotShowItem,
    sequence_number: int,
    quantity: int,
    auction_start_cents: int,
    title_override: str | None,
    sale_format: str = "AUCTION",
) -> WhatnotShowItem:
    _ensure_editable(show_item.show)
    if sequence_number < 1:
        raise ValueError("Run order must be 1 or greater")
    if quantity < 1 or quantity > show_item.inventory_item.quantity_on_hand:
        raise ValueError("Quantity exceeds inventory on hand")
    if auction_start_cents < 0:
        raise ValueError("Auction start cannot be negative")
    sale_format = sale_format.upper().strip()
    if sale_format not in TYPE_MAP:
        raise ValueError("Unsupported Whatnot sale format")

    show_item.sequence_number = sequence_number
    show_item.quantity_planned = quantity
    show_item.auction_start_cents = auction_start_cents
    show_item.title_override = (title_override or "").strip() or None
    show_item.sale_format = sale_format
    db.flush()
    return show_item


def remove_show_item(db: Session, show_item: WhatnotShowItem) -> None:
    _ensure_editable(show_item.show)
    inventory = show_item.inventory_item
    show = show_item.show
    db.add(InventoryEvent(
        inventory_id=inventory.inventory_id,
        event_type="WHATNOT_SHOW_REMOVE",
        from_status=inventory.status,
        to_status=inventory.status,
        quantity_delta=0,
        marketplace="WHATNOT",
        reference_type="WHATNOT_SHOW",
        reference_id=show.show_id,
        message=f"Removed from {show.show_number}",
    ))
    db.delete(show_item)
    db.flush()


def set_show_status(db: Session, show: WhatnotShow, status: str) -> WhatnotShow:
    status = status.upper().strip()
    allowed = {
        WhatnotShowStatus.DRAFT.value,
        WhatnotShowStatus.READY.value,
        WhatnotShowStatus.LIVE.value,
        WhatnotShowStatus.COMPLETED.value,
        WhatnotShowStatus.CANCELLED.value,
    }
    if status not in allowed:
        raise ValueError("Invalid Whatnot show status")
    if show.status == WhatnotShowStatus.COMPLETED.value and status != show.status:
        raise ValueError("Completed shows cannot be reopened")
    show.status = status
    db.flush()
    return show


def _default_title(item: WhatnotShowItem) -> str:
    inventory = item.inventory_item
    card = inventory.card
    if card is None:
        return inventory.sku
    parts = [card.name, card.card_number]
    if card.card_set:
        parts.append(card.card_set.name)
    if card.rarity:
        parts.append(card.rarity)
    if inventory.is_graded and inventory.grading_company and inventory.grade:
        parts.append(f"{inventory.grading_company} {inventory.grade}")
    return " - ".join(part for part in parts if part)


def _description(item: WhatnotShowItem) -> str:
    inventory = item.inventory_item
    card = inventory.card
    fields = [f"SKU: {inventory.sku}"]
    if card and card.card_set:
        fields.append(f"Set: {card.card_set.name}")
    if card:
        fields.append(f"Card: {card.name} {card.card_number}")
        if card.rarity:
            fields.append(f"Rarity: {card.rarity}")
    if inventory.condition:
        fields.append(f"Condition: {inventory.condition}")
    if inventory.variant_label:
        fields.append(f"Variant: {inventory.variant_label}")
    return " | ".join(fields)


def export_show_csv(db: Session, show_id: int) -> tuple[WhatnotShow, str]:
    show = get_show(db, show_id, with_items=True)
    if not show.items:
        raise ValueError("Cannot export an empty show")

    rows = sorted(show.items, key=lambda x: (x.sequence_number or 999999, x.show_item_id))
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=WHATNOT_HEADERS)
    writer.writeheader()

    for row_number, item in enumerate(rows, start=2):
        inventory = item.inventory_item
        images = [
            image.external_url for image in sorted(inventory.images, key=lambda x: x.image_order)
            if image.external_url and image.external_url.startswith("https://")
        ][:8]
        price_cents = item.auction_start_cents
        if item.sale_format == "BUY_IT_NOW" and inventory.target_price_cents is not None:
            price_cents = inventory.target_price_cents

        row = {
            "Category": DEFAULT_CATEGORY,
            "Sub Category": DEFAULT_SUB_CATEGORY,
            "Title": item.title_override or _default_title(item),
            "Description": _description(item),
            "Quantity": item.quantity_planned,
            "Type": TYPE_MAP[item.sale_format],
            "Price": _money(price_cents),
            "Shipping Profile": DEFAULT_SHIPPING_PROFILE,
            "Offerable": "FALSE",
            "Hazmat": "Not Hazmat",
            "Condition": CONDITION_MAP.get((inventory.condition or "").upper(), inventory.condition or "Near Mint"),
            "Cost Per Item": _money(inventory.unit_cost_cents),
            "SKU": inventory.sku,
        }
        for index in range(8):
            row[f"Image URL {index + 1}"] = images[index] if index < len(images) else ""
        writer.writerow(row)
        item.export_row_number = row_number

    show.export_generated_at = utcnow()
    if show.status == WhatnotShowStatus.DRAFT.value:
        show.status = WhatnotShowStatus.READY.value
    db.flush()
    return show, output.getvalue()


def export_filename(show: WhatnotShow) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", show.name).strip("-")[:60] or "show"
    return f"{show.show_number}-{name}-whatnot.csv"
