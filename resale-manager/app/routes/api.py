from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import __version__
from app.core.database import get_db
from app.models import InventoryItem


router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/inventory")
def inventory(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(
        select(InventoryItem)
        .options(joinedload(InventoryItem.card), joinedload(InventoryItem.location))
        .order_by(InventoryItem.inventory_id.desc())
    ).all()

    return [
        {
            "inventory_id": item.inventory_id,
            "sku": item.sku,
            "card_name": item.card.name if item.card else None,
            "status": item.status,
            "condition": item.condition,
            "quantity_on_hand": item.quantity_on_hand,
            "unit_cost_cents": item.unit_cost_cents,
            "market_value_cents": item.market_value_cents,
            "location": item.location.location_code if item.location else None,
        }
        for item in rows
    ]
