from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import InventoryItem, Purchase, Sale


router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    inventory_count = db.scalar(select(func.count(InventoryItem.inventory_id))) or 0
    available_count = db.scalar(
        select(func.count(InventoryItem.inventory_id)).where(InventoryItem.quantity_on_hand > 0)
    ) or 0
    purchase_count = db.scalar(select(func.count(Purchase.purchase_id))) or 0
    sale_count = db.scalar(select(func.count(Sale.sale_id))) or 0

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "inventory_count": inventory_count,
            "available_count": available_count,
            "purchase_count": purchase_count,
            "sale_count": sale_count,
        },
    )


@router.get("/inventory")
def inventory_page(request: Request, db: Session = Depends(get_db)):
    items = db.scalars(
        select(InventoryItem)
        .options(joinedload(InventoryItem.card), joinedload(InventoryItem.location))
        .order_by(InventoryItem.inventory_id.desc())
    ).all()
    return templates.TemplateResponse(request=request, name="inventory.html", context={"items": items})


@router.get("/purchases")
def purchases_page(request: Request, db: Session = Depends(get_db)):
    purchases = db.scalars(select(Purchase).order_by(Purchase.purchase_date.desc())).all()
    return templates.TemplateResponse(request=request, name="purchases.html", context={"purchases": purchases})
