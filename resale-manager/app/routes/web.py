from __future__ import annotations

from datetime import date
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.enums import InventoryStatus, InventoryType, TrackingMode
from app.models import Card, CardSet, InventoryItem, Purchase, Sale, StorageLocation
from app.services.intake import (
    create_inventory_item,
    create_purchase,
    create_storage_location,
    find_or_create_card,
    money_to_cents,
    purchase_allocated_cents,
    refresh_purchase_allocation,
    transition_inventory,
)
from app.services.tcgdex import TCGdexService

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _purchase_or_404(db: Session, purchase_id: int) -> Purchase:
    purchase = db.scalar(
        select(Purchase)
        .where(Purchase.purchase_id == purchase_id)
        .options(joinedload(Purchase.inventory_items).joinedload(InventoryItem.card))
    )
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return purchase


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    inventory_count = db.scalar(select(func.count(InventoryItem.inventory_id))) or 0
    available_count = db.scalar(select(func.count(InventoryItem.inventory_id)).where(InventoryItem.quantity_on_hand > 0)) or 0
    purchase_count = db.scalar(select(func.count(Purchase.purchase_id))) or 0
    sale_count = db.scalar(select(func.count(Sale.sale_id))) or 0
    whatnot_queue = db.scalar(select(func.count(InventoryItem.inventory_id)).where(InventoryItem.status == InventoryStatus.WHATNOT_QUEUE.value)) or 0
    ebay_queue = db.scalar(select(func.count(InventoryItem.inventory_id)).where(InventoryItem.status == InventoryStatus.EBAY_QUEUE.value)) or 0
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "inventory_count": inventory_count, "available_count": available_count,
        "purchase_count": purchase_count, "sale_count": sale_count,
        "whatnot_queue": whatnot_queue, "ebay_queue": ebay_queue,
    })


@router.get("/inventory")
def inventory_page(
    request: Request,
    status: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    direction: str = "asc",
    db: Session = Depends(get_db),
):
    stmt = (
        select(InventoryItem)
        .outerjoin(InventoryItem.card)
        .outerjoin(Card.card_set)
        .outerjoin(InventoryItem.location)
        .options(
            joinedload(InventoryItem.card).joinedload(Card.card_set),
            joinedload(InventoryItem.location),
            joinedload(InventoryItem.purchase),
        )
    )
    if status:
        stmt = stmt.where(InventoryItem.status == status.upper())

    search_query = (q or "").strip()
    if search_query:
        term = f"%{search_query}%"
        stmt = stmt.where(
            or_(
                InventoryItem.sku.ilike(term),
                InventoryItem.status.ilike(term),
                InventoryItem.condition.ilike(term),
                InventoryItem.finish.ilike(term),
                InventoryItem.variant_label.ilike(term),
                InventoryItem.language.ilike(term),
                Card.name.ilike(term),
                Card.card_number.ilike(term),
                Card.rarity.ilike(term),
                CardSet.name.ilike(term),
                CardSet.set_code.ilike(term),
                StorageLocation.location_code.ilike(term),
                StorageLocation.name.ilike(term),
            )
        )

    sort_key = (sort or "").strip().lower()
    sort_direction = "desc" if direction.lower() == "desc" else "asc"
    sort_columns = {
        "sku": InventoryItem.sku,
        "card": Card.name,
        "set": CardSet.set_code,
        "number": Card.card_number,
        "status": InventoryItem.status,
        "condition": InventoryItem.condition,
        "qty": InventoryItem.quantity_on_hand,
        "cost": InventoryItem.unit_cost_cents,
        "market": InventoryItem.market_value_cents,
        "updated": InventoryItem.market_value_updated_at,
        "location": StorageLocation.location_code,
    }
    sort_column = sort_columns.get(sort_key)
    if sort_column is not None:
        order_expression = sort_column.desc() if sort_direction == "desc" else sort_column.asc()
        stmt = stmt.order_by(order_expression.nullslast(), InventoryItem.inventory_id.desc())
    else:
        sort_key = ""
        sort_direction = "asc"
        stmt = stmt.order_by(InventoryItem.inventory_id.desc())

    items = db.scalars(stmt).unique().all()
    total_market_cents = sum((item.market_value_cents or 0) * item.quantity_on_hand for item in items)
    return templates.TemplateResponse(request=request, name="inventory.html", context={
        "items": items,
        "status_filter": status,
        "search_query": search_query,
        "sort_key": sort_key,
        "sort_direction": sort_direction,
        "total_market_cents": total_market_cents,
        "pricing_checked": request.query_params.get("pricing_checked"),
        "pricing_matched": request.query_params.get("pricing_matched"),
        "pricing_priced": request.query_params.get("pricing_priced"),
        "pricing_unmatched": request.query_params.get("pricing_unmatched"),
        "pricing_error": request.query_params.get("pricing_error"),
    })


@router.post("/inventory/pricing/refresh")
def inventory_refresh_prices(db: Session = Depends(get_db)):
    try:
        summary = TCGdexService().refresh_inventory(db)
        db.commit()
        return RedirectResponse(
            url=(
                "/inventory?pricing_checked={checked}&pricing_matched={matched}"
                "&pricing_priced={priced}&pricing_unmatched={unmatched}"
            ).format(**summary),
            status_code=303,
        )
    except Exception as exc:
        db.rollback()
        return RedirectResponse(url=f"/inventory?pricing_error={quote(str(exc))}", status_code=303)


@router.post("/inventory/{inventory_id}/status")
def inventory_status(inventory_id: int, status: str = Form(...), db: Session = Depends(get_db)):
    item = db.get(InventoryItem, inventory_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    transition_inventory(db, item, status)
    db.commit()
    return RedirectResponse(url="/inventory", status_code=303)


@router.get("/purchases")
def purchases_page(request: Request, db: Session = Depends(get_db)):
    purchases = db.scalars(select(Purchase).order_by(Purchase.purchase_date.desc(), Purchase.purchase_id.desc())).all()
    allocation = {p.purchase_id: purchase_allocated_cents(db, p.purchase_id) for p in purchases}
    return templates.TemplateResponse(request=request, name="purchases.html", context={"purchases": purchases, "allocation": allocation})


@router.get("/purchases/new")
def purchase_new_page(request: Request):
    return templates.TemplateResponse(request=request, name="purchase_new.html", context={"today": date.today().isoformat(), "error": None})


@router.post("/purchases/new")
def purchase_create(
    request: Request,
    purchase_date: str = Form(...), source_type: str = Form(...), source_name: str = Form(""),
    external_order_id: str = Form(""), subtotal: str = Form("0"), sales_tax: str = Form("0"),
    shipping: str = Form("0"), buyer_fees: str = Form("0"), discount: str = Form("0"),
    notes: str = Form(""), db: Session = Depends(get_db),
):
    try:
        purchase = create_purchase(
            db, purchase_date=date.fromisoformat(purchase_date), source_type=source_type,
            source_name=source_name, external_order_id=external_order_id,
            subtotal_cents=money_to_cents(subtotal), sales_tax_cents=money_to_cents(sales_tax),
            shipping_cents=money_to_cents(shipping), buyer_fees_cents=money_to_cents(buyer_fees),
            discount_cents=money_to_cents(discount), notes=notes,
        )
        db.commit()
        return RedirectResponse(url=f"/purchases/{purchase.purchase_id}", status_code=303)
    except (ValueError, TypeError) as exc:
        db.rollback()
        return templates.TemplateResponse(request=request, name="purchase_new.html", status_code=400,
            context={"today": purchase_date, "error": str(exc)})


@router.get("/purchases/{purchase_id}")
def purchase_detail(purchase_id: int, request: Request, db: Session = Depends(get_db)):
    purchase = _purchase_or_404(db, purchase_id)
    allocated, remaining = refresh_purchase_allocation(db, purchase)
    locations = db.scalars(select(StorageLocation).where(StorageLocation.active == 1).order_by(StorageLocation.location_code)).all()
    db.commit()
    return templates.TemplateResponse(request=request, name="purchase_detail.html", context={
        "purchase": purchase, "allocated": allocated, "remaining": remaining,
        "locations": locations, "error": request.query_params.get("error"),
        "inventory_statuses": [InventoryStatus.READY.value, InventoryStatus.WHATNOT_QUEUE.value, InventoryStatus.EBAY_QUEUE.value, InventoryStatus.HOLD.value, InventoryStatus.PERSONAL.value],
    })


@router.post("/purchases/{purchase_id}/inventory")
def purchase_add_inventory(
    purchase_id: int, set_code: str = Form(...), set_name: str = Form(...), card_name: str = Form(...),
    card_number: str = Form(...), rarity: str = Form(""), language: str = Form("EN"), condition: str = Form("NM"),
    finish: str = Form(""), variant_label: str = Form(""), grading_company: str = Form(""), grade: str = Form(""),
    cert_number: str = Form(""), quantity: int = Form(1), unit_cost: str = Form("0"), market_value: str = Form(""),
    target_price: str = Form(""), minimum_price: str = Form(""), location_id: str = Form(""),
    destination_status: str = Form(InventoryStatus.READY.value), tracking_mode: str = Form(TrackingMode.SERIALIZED.value),
    notes: str = Form(""), db: Session = Depends(get_db),
):
    purchase = db.get(Purchase, purchase_id)
    if purchase is None:
        raise HTTPException(status_code=404, detail="Purchase not found")
    try:
        card = find_or_create_card(db, set_code=set_code, set_name=set_name, card_name=card_name,
                                   card_number=card_number, rarity=rarity, language=language)
        create_inventory_item(
            db, purchase=purchase, card=card, location_id=int(location_id) if location_id else None,
            condition=condition, language=language, finish=finish, variant_label=variant_label,
            grading_company=grading_company or None, grade=grade or None, cert_number=cert_number,
            quantity=quantity, unit_cost_cents=money_to_cents(unit_cost),
            market_value_cents=money_to_cents(market_value) if market_value.strip() else None,
            target_price_cents=money_to_cents(target_price) if target_price.strip() else None,
            minimum_price_cents=money_to_cents(minimum_price) if minimum_price.strip() else None,
            destination_status=destination_status,
            inventory_type=InventoryType.SINGLE_CARD.value if tracking_mode == TrackingMode.SERIALIZED.value else InventoryType.BULK_LOT.value,
            tracking_mode=tracking_mode, notes=notes,
        )
        db.commit()
        return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(url=f"/purchases/{purchase_id}?error={quote(str(exc))}", status_code=303)


@router.get("/storage")
def storage_page(request: Request, db: Session = Depends(get_db)):
    locations = db.scalars(select(StorageLocation).order_by(StorageLocation.location_code)).all()
    return templates.TemplateResponse(request=request, name="storage.html", context={"locations": locations, "error": None})


@router.post("/storage")
def storage_create(request: Request, location_code: str = Form(...), name: str = Form(...),
                   location_type: str = Form("SLOT"), parent_location_id: str = Form(""),
                   notes: str = Form(""), db: Session = Depends(get_db)):
    try:
        create_storage_location(db, location_code=location_code, name=name, location_type=location_type,
                                parent_location_id=int(parent_location_id) if parent_location_id else None, notes=notes)
        db.commit()
        return RedirectResponse(url="/storage", status_code=303)
    except ValueError as exc:
        db.rollback()
        locations = db.scalars(select(StorageLocation).order_by(StorageLocation.location_code)).all()
        return templates.TemplateResponse(request=request, name="storage.html", status_code=400,
                                          context={"locations": locations, "error": str(exc)})
