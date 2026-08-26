from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import InventoryItem, Sale, WhatnotShowItem


router = APIRouter(tags=["sales"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/sales")
def sales_page(request: Request, db: Session = Depends(get_db)):
    rows = db.execute(
        select(Sale)
        .options(
            joinedload(Sale.inventory_item).joinedload(InventoryItem.card),
            joinedload(Sale.order),
            joinedload(Sale.show_item).joinedload(WhatnotShowItem.show),
        )
        .order_by(Sale.sold_at.desc(), Sale.sale_id.desc())
    ).unique().scalars().all()

    gross_cents = sum(row.gross_item_cents for row in rows)
    cost_basis_cents = sum(row.cost_basis_cents for row in rows)
    fee_cents = sum(
        row.marketplace_fee_cents
        + row.processing_fee_cents
        + row.shipping_cost_allocated_cents
        + row.packaging_cost_allocated_cents
        + row.discount_cents
        + row.refund_cents
        + row.other_cost_cents
        for row in rows
    )
    profit_cents = sum(row.realized_profit_cents for row in rows)

    return templates.TemplateResponse(
        request=request,
        name="sales.html",
        context={
            "sales": rows,
            "gross_cents": gross_cents,
            "cost_basis_cents": cost_basis_cents,
            "fee_cents": fee_cents,
            "profit_cents": profit_cents,
        },
    )
