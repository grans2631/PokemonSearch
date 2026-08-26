from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.enums import InventoryStatus
from app.models import Card, InventoryItem, Listing, ListingItem
from app.services.ebay import EbayError, EbayService
from app.services.intake import money_to_cents


router = APIRouter(prefix="/ebay", tags=["ebay"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _service() -> EbayService:
    return EbayService()


def _redirect_error(path: str, message: str) -> RedirectResponse:
    separator = "&" if "?" in path else "?"
    return RedirectResponse(url=f"{path}{separator}error={quote(message)}", status_code=303)


@router.get("")
def ebay_page(request: Request, db: Session = Depends(get_db)):
    service = _service()
    status = service.connection_status()
    selected = service.listing_settings(db)
    snapshot = None
    api_error = None
    if status["connected"]:
        try:
            snapshot = service.get_account_snapshot()
        except EbayError as exc:
            api_error = str(exc)
    return templates.TemplateResponse(
        request=request,
        name="ebay.html",
        context={
            "status": status,
            "snapshot": snapshot,
            "selected": selected,
            "environment": settings.ebay_environment,
            "marketplace_id": settings.ebay_marketplace_id,
            "api_error": api_error,
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
        },
    )


@router.get("/connect")
def ebay_connect():
    try:
        return RedirectResponse(url=_service().begin_authorization(), status_code=302)
    except EbayError as exc:
        return _redirect_error("/ebay", str(exc))


@router.get("/oauth/callback")
def ebay_oauth_callback(code: str = "", state: str = "", error: str = ""):
    if error:
        return _redirect_error("/ebay", f"eBay authorization declined or failed: {error}")
    if not code or not state:
        return _redirect_error("/ebay", "eBay OAuth callback did not include code and state")
    try:
        _service().complete_authorization(code=code, state=state)
        return RedirectResponse(url="/ebay?message=eBay%20account%20connected", status_code=303)
    except EbayError as exc:
        return _redirect_error("/ebay", str(exc))


@router.post("/disconnect")
def ebay_disconnect():
    _service().disconnect()
    return RedirectResponse(url="/ebay?message=eBay%20account%20disconnected", status_code=303)


@router.post("/settings")
def ebay_save_settings(
    payment_policy_id: str = Form(""),
    fulfillment_policy_id: str = Form(""),
    return_policy_id: str = Form(""),
    merchant_location_key: str = Form(""),
    category_id: str = Form(""),
    db: Session = Depends(get_db),
):
    if not all([payment_policy_id.strip(), fulfillment_policy_id.strip(), return_policy_id.strip(), merchant_location_key.strip(), category_id.strip()]):
        return _redirect_error("/ebay", "Select all three policies, an inventory location, and a category ID")
    service = _service()
    service.save_listing_settings(
        db,
        payment_policy_id=payment_policy_id,
        fulfillment_policy_id=fulfillment_policy_id,
        return_policy_id=return_policy_id,
        merchant_location_key=merchant_location_key,
        category_id=category_id,
    )
    db.commit()
    return RedirectResponse(url="/ebay?message=eBay%20listing%20defaults%20saved", status_code=303)


@router.get("/queue")
def ebay_queue(request: Request, db: Session = Depends(get_db)):
    service = _service()
    items = db.scalars(
        select(InventoryItem)
        .where(InventoryItem.status == InventoryStatus.EBAY_QUEUE.value, InventoryItem.quantity_on_hand > 0)
        .options(
            joinedload(InventoryItem.card).joinedload(Card.card_set),
            joinedload(InventoryItem.images),
            joinedload(InventoryItem.location),
        )
        .order_by(InventoryItem.inventory_id)
    ).unique().all()
    listings = db.execute(
        select(ListingItem, Listing)
        .join(Listing, Listing.listing_id == ListingItem.listing_id)
        .where(
            Listing.marketplace == "EBAY",
            Listing.status.in_(["DRAFT", "PENDING", "ACTIVE"]),
        )
        .order_by(Listing.listing_id.desc())
    ).all()
    by_inventory: dict[int, Listing] = {}
    for link, listing in listings:
        by_inventory.setdefault(link.inventory_id, listing)
    selected = service.listing_settings(db)
    previews = {
        item.inventory_id: {
            "title": service.build_title(item),
            "price_cents": item.target_price_cents or item.market_value_cents or 0,
            "image_count": len([image for image in item.images if image.external_url and image.external_url.startswith("https://")]),
        }
        for item in items
    }
    return templates.TemplateResponse(
        request=request,
        name="ebay_queue.html",
        context={
            "items": items,
            "listings": by_inventory,
            "previews": previews,
            "selected": selected,
            "connection": service.connection_status(),
            "error": request.query_params.get("error"),
            "message": request.query_params.get("message"),
        },
    )


@router.post("/queue/{inventory_id}/draft")
def ebay_create_draft(
    inventory_id: int,
    title: str = Form(""),
    price: str = Form(""),
    category_id: str = Form(""),
    db: Session = Depends(get_db),
):
    inventory = db.get(InventoryItem, inventory_id)
    if inventory is None:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    service = _service()
    try:
        cents = money_to_cents(price)
        selected_category = category_id.strip() or service.listing_settings(db)["category_id"]
        listing = service.create_local_draft(
            db,
            inventory=inventory,
            title=title,
            price_cents=cents,
            category_id=selected_category,
        )
        # create_local_draft stores this for a new listing. Re-save it here as
        # well so editing an existing local draft can change its eBay category.
        service.set_setting(db, f"ebay.listing.{listing.listing_id}.category_id", selected_category)
        db.commit()
        return RedirectResponse(url=f"/ebay/queue?message=Draft%20{listing.listing_id}%20saved", status_code=303)
    except (ValueError, EbayError) as exc:
        db.rollback()
        return _redirect_error("/ebay/queue", str(exc))


@router.post("/listings/{listing_id}/sync")
def ebay_sync_draft(listing_id: int, db: Session = Depends(get_db)):
    service = _service()
    try:
        result = service.sync_draft_to_ebay(db, listing_id=listing_id)
        db.commit()
        return RedirectResponse(
            url=f"/ebay/queue?message=eBay%20offer%20draft%20{quote(result.external_offer_id or '')}%20synced%20(not%20published)",
            status_code=303,
        )
    except EbayError as exc:
        db.rollback()
        listing = db.get(Listing, listing_id)
        if listing is not None:
            listing.last_error = str(exc)
            db.commit()
        return _redirect_error("/ebay/queue", str(exc))
