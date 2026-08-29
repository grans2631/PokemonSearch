from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.models import InventoryItem, WhatnotShow, WhatnotShowItem
from app.services.intake import money_to_cents
from app.services.whatnot import (
    add_show_item,
    create_show,
    eligible_inventory,
    export_filename,
    export_show_csv,
    get_show,
    remove_show_item,
    set_show_status,
    update_show_item,
)
from app.services.whatnot_reconcile import import_show_report


router = APIRouter(prefix="/whatnot", tags=["whatnot"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


def _show_or_404(db: Session, show_id: int, *, with_items: bool = False) -> WhatnotShow:
    try:
        return get_show(db, show_id, with_items=with_items)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("")
def shows_page(request: Request, db: Session = Depends(get_db)):
    shows = db.execute(
        select(WhatnotShow)
        .options(joinedload(WhatnotShow.items))
        .order_by(WhatnotShow.created_at.desc(), WhatnotShow.show_id.desc())
    ).unique().scalars().all()
    return templates.TemplateResponse(
        request=request,
        name="whatnot_shows.html",
        context={"shows": shows},
    )


@router.get("/shows/new")
def show_new_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="whatnot_show_new.html",
        context={"error": None},
    )


@router.post("/shows/new")
def show_create(
    request: Request,
    name: str = Form(...),
    scheduled_at: str = Form(""),
    theme: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    try:
        scheduled = datetime.fromisoformat(scheduled_at) if scheduled_at.strip() else None
        show = create_show(db, name=name, scheduled_at=scheduled, theme=theme, notes=notes)
        db.commit()
        return RedirectResponse(url=f"/whatnot/shows/{show.show_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="whatnot_show_new.html",
            status_code=400,
            context={"error": str(exc)},
        )


@router.get("/shows/{show_id}")
def show_detail(show_id: int, request: Request, db: Session = Depends(get_db)):
    show = _show_or_404(db, show_id, with_items=True)
    queued = eligible_inventory(db)
    assigned_ids = {item.inventory_id for item in show.items}
    queued = [item for item in queued if item.inventory_id not in assigned_ids]
    return templates.TemplateResponse(
        request=request,
        name="whatnot_show_detail.html",
        context={
            "show": show,
            "queued": queued,
            "error": request.query_params.get("error"),
            "reconciled": request.query_params.get("reconciled"),
            "duplicate": request.query_params.get("duplicate"),
            "sold_units": request.query_params.get("sold_units"),
            "unsold_items": request.query_params.get("unsold_items"),
            "gross": request.query_params.get("gross"),
            "fees": request.query_params.get("fees"),
            "profit": request.query_params.get("profit"),
        },
    )


@router.post("/shows/{show_id}/items")
def show_add_items(
    show_id: int,
    inventory_ids: list[int] | None = Form(None),
    default_start: str = Form("1.00"),
    db: Session = Depends(get_db),
):
    show = _show_or_404(db, show_id)
    if not inventory_ids:
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote('Select at least one inventory item')}",
            status_code=303,
        )
    try:
        start_cents = money_to_cents(default_start)
        for inventory_id in inventory_ids:
            inventory = db.get(InventoryItem, inventory_id)
            if inventory is None:
                raise ValueError(f"Inventory item {inventory_id} not found")
            add_show_item(
                db,
                show=show,
                inventory=inventory,
                quantity=1,
                auction_start_cents=start_cents,
            )
        db.commit()
        return RedirectResponse(url=f"/whatnot/shows/{show_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote(str(exc))}",
            status_code=303,
        )


@router.post("/shows/{show_id}/items/{show_item_id}")
def show_update_item(
    show_id: int,
    show_item_id: int,
    sequence_number: int = Form(...),
    quantity: int = Form(1),
    auction_start: str = Form("1.00"),
    title_override: str = Form(""),
    sale_format: str = Form("AUCTION"),
    db: Session = Depends(get_db),
):
    show_item = db.get(WhatnotShowItem, show_item_id)
    if show_item is None or show_item.show_id != show_id:
        raise HTTPException(status_code=404, detail="Whatnot show item not found")
    try:
        update_show_item(
            db,
            show_item=show_item,
            sequence_number=sequence_number,
            quantity=quantity,
            auction_start_cents=money_to_cents(auction_start),
            title_override=title_override,
            sale_format=sale_format,
        )
        db.commit()
        return RedirectResponse(url=f"/whatnot/shows/{show_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote(str(exc))}",
            status_code=303,
        )


@router.post("/shows/{show_id}/items/{show_item_id}/remove")
def show_remove_item(
    show_id: int,
    show_item_id: int,
    db: Session = Depends(get_db),
):
    show_item = db.get(WhatnotShowItem, show_item_id)
    if show_item is None or show_item.show_id != show_id:
        raise HTTPException(status_code=404, detail="Whatnot show item not found")
    try:
        remove_show_item(db, show_item)
        db.commit()
        return RedirectResponse(url=f"/whatnot/shows/{show_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote(str(exc))}",
            status_code=303,
        )


@router.post("/shows/{show_id}/status")
def show_status(
    show_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db),
):
    show = _show_or_404(db, show_id)
    try:
        set_show_status(db, show, status)
        db.commit()
        return RedirectResponse(url=f"/whatnot/shows/{show_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote(str(exc))}",
            status_code=303,
        )


@router.get("/shows/{show_id}/export.csv")
def show_export(show_id: int, db: Session = Depends(get_db)):
    try:
        show, csv_text = export_show_csv(db, show_id)
        filename = export_filename(show)
        db.commit()
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote(str(exc))}",
            status_code=303,
        )


@router.post("/shows/{show_id}/reconcile")
async def show_reconcile(
    show_id: int,
    report: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = report.filename or "whatnot-show-report.csv"
    try:
        content = await report.read()
        summary = import_show_report(db, show_id=show_id, filename=filename, content=content)
        db.commit()
        params = {
            "reconciled": "1",
            "duplicate": "1" if summary.duplicate else "0",
            "sold_units": str(summary.sold_units),
            "unsold_items": str(summary.unsold_items),
            "gross": f"{summary.gross_cents / 100:.2f}",
            "fees": f"{summary.fee_cents / 100:.2f}",
            "profit": f"{summary.realized_profit_cents / 100:.2f}",
        }
        return RedirectResponse(url=f"/whatnot/shows/{show_id}?{urlencode(params)}", status_code=303)
    except ValueError as exc:
        db.rollback()
        return RedirectResponse(
            url=f"/whatnot/shows/{show_id}?error={quote(str(exc))}",
            status_code=303,
        )
