from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.enums import InventoryStatus, WhatnotResultStatus, WhatnotShowStatus
from app.models import IntegrationRun, InventoryEvent, InventoryItem, Order, Sale, WhatnotShow, WhatnotShowItem
from app.models.base import utcnow


_CANCELLED_STATUSES = {"cancelled", "canceled", "refunded", "void", "voided"}

_ALIASES = {
    "sku": {"sku", "seller sku", "product sku", "inventory sku"},
    "order_id": {"order id", "order number", "order numeric id", "order"},
    "buyer": {"buyer", "buyer username", "username", "customer"},
    "quantity": {"quantity", "qty", "quantity sold", "units"},
    "sale_price": {"sale price", "sold price", "item price", "price", "gross item", "gross sale", "gross sales"},
    "commission_fee": {"commission fee", "whatnot commission", "whatnot commission fee", "marketplace fee", "seller fee"},
    "processing_fee": {"payment processing fee", "processing fee", "payment fee"},
    "total_fees": {"fees", "total fees", "seller fees", "total seller fees"},
    "seller_shipping": {"seller paid shipping", "shipping cost", "shipping label cost", "seller shipping"},
    "sold_at": {"sold at", "sale date", "sold date", "order placed at", "order placed at utc", "processed date", "order date", "created at"},
    "status": {"status", "order status", "sale status"},
    "title": {"title", "product name", "item name", "listing title"},
    "description": {"description", "product description", "item description"},
}


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def _header_map(fieldnames: Iterable[str]) -> dict[str, str]:
    normalized = {_norm(name): name for name in fieldnames if name}
    result: dict[str, str] = {}
    for canonical, aliases in _ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                result[canonical] = normalized[alias]
                break
    return result


def _cell(row: dict[str, str], header_map: dict[str, str], key: str) -> str:
    header = header_map.get(key)
    return (row.get(header, "") if header else "").strip()


def _money_to_cents(value: str | None) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    negative = text.startswith("(") and text.endswith(")")
    cleaned = re.sub(r"[^0-9.\-]", "", text.replace(",", ""))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return 0
    cents = int(round(float(cleaned) * 100))
    if negative and cents > 0:
        cents = -cents
    return cents


def _positive_cost(value: str | None) -> int:
    return abs(_money_to_cents(value))


def _quantity(value: str | None, *, sold: bool) -> int:
    text = (value or "").strip()
    if not text:
        return 1 if sold else 0
    try:
        qty = int(float(text))
    except ValueError:
        return 1 if sold else 0
    return max(qty, 0)


def _parse_datetime(value: str | None, fallback: datetime) -> datetime:
    text = (value or "").strip()
    if not text:
        return fallback
    normalized = text.replace("Z", "+00:00")
    for parser in (
        lambda: datetime.fromisoformat(normalized),
        lambda: datetime.strptime(text, "%Y-%m-%d %H:%M:%S"),
        lambda: datetime.strptime(text, "%m/%d/%Y %H:%M:%S"),
        lambda: datetime.strptime(text, "%m/%d/%Y %I:%M %p"),
        lambda: datetime.strptime(text, "%Y-%m-%d"),
    ):
        try:
            dt = parser()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return fallback


def _decode_csv(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("cp1252")
    if not text.strip():
        raise ValueError("The Whatnot Show Report is empty")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise ValueError("The Whatnot Show Report does not contain a header row")
    rows = [dict(row) for row in reader if any((value or "").strip() for value in row.values())]
    return rows, list(reader.fieldnames)


def _known_sku_from_row(row: dict[str, str], header_map: dict[str, str], known: dict[str, WhatnotShowItem]) -> str | None:
    direct = _cell(row, header_map, "sku")
    if direct:
        candidate = direct.upper()
        if candidate in known:
            return candidate
    haystack = " | ".join(str(value or "") for value in row.values()).upper()
    matches = [sku for sku in known if sku in haystack]
    if len(matches) == 1:
        return matches[0]
    return None


@dataclass(slots=True)
class ReconcileSummary:
    duplicate: bool = False
    rows_read: int = 0
    rows_matched: int = 0
    sale_records: int = 0
    sold_units: int = 0
    sold_out_items: int = 0
    ebay_queue_items: int = 0
    unsold_items: int = 0
    gross_cents: int = 0
    fee_cents: int = 0
    cost_basis_cents: int = 0
    realized_profit_cents: int = 0
    ignored_rows: int = 0


def _show_with_items(db: Session, show_id: int) -> WhatnotShow:
    stmt = (
        select(WhatnotShow)
        .where(WhatnotShow.show_id == show_id)
        .options(
            joinedload(WhatnotShow.items)
            .joinedload(WhatnotShowItem.inventory_item)
            .joinedload(InventoryItem.card)
        )
    )
    show = db.execute(stmt).unique().scalar_one_or_none()
    if show is None:
        raise ValueError("Whatnot show not found")
    return show


def import_show_report(
    db: Session,
    *,
    show_id: int,
    filename: str,
    content: bytes,
) -> ReconcileSummary:
    if len(content) > 10 * 1024 * 1024:
        raise ValueError("Whatnot Show Report exceeds the 10 MB import limit")

    digest = hashlib.sha256(content).hexdigest()
    prior = db.scalar(
        select(IntegrationRun).where(
            IntegrationRun.integration == "WHATNOT",
            IntegrationRun.operation == "SHOW_REPORT_IMPORT",
            IntegrationRun.file_sha256 == digest,
            IntegrationRun.status == "COMPLETED",
        )
    )
    if prior:
        return ReconcileSummary(duplicate=True, rows_read=prior.records_read, sale_records=prior.records_written)

    show = _show_with_items(db, show_id)
    if show.status == WhatnotShowStatus.RECONCILED.value:
        raise ValueError("This Whatnot show has already been reconciled. Re-import of a different report is blocked in v0.4.")
    if show.status != WhatnotShowStatus.COMPLETED.value:
        raise ValueError("Mark the Whatnot show COMPLETED before importing its final Show Report")
    if not show.items:
        raise ValueError("Cannot reconcile a Whatnot show with no inventory")

    rows, fieldnames = _decode_csv(content)
    header_map = _header_map(fieldnames)
    if "sale_price" not in header_map:
        raise ValueError("Could not identify a sale-price column in the Whatnot Show Report")

    known = {item.inventory_item.sku.upper(): item for item in show.items}
    now = utcnow()
    run = IntegrationRun(
        integration="WHATNOT",
        operation="SHOW_REPORT_IMPORT",
        direction="IMPORT",
        filename=(filename or "whatnot-show-report.csv")[:250],
        file_sha256=digest,
        status="RUNNING",
        records_read=len(rows),
        records_written=0,
    )
    db.add(run)
    db.flush()

    summary = ReconcileSummary(rows_read=len(rows))
    unmatched_sold_rows: list[int] = []

    for row_index, row in enumerate(rows, start=2):
        sale_price_cents = max(_money_to_cents(_cell(row, header_map, "sale_price")), 0)
        status_text = _norm(_cell(row, header_map, "status"))
        cancelled = any(token in status_text for token in _CANCELLED_STATUSES)
        looks_sold = sale_price_cents > 0 and not cancelled

        sku = _known_sku_from_row(row, header_map, known)
        if not sku:
            if looks_sold:
                unmatched_sold_rows.append(row_index)
            else:
                summary.ignored_rows += 1
            continue

        show_item = known[sku]
        inventory = show_item.inventory_item
        summary.rows_matched += 1

        if not looks_sold:
            continue

        qty = _quantity(_cell(row, header_map, "quantity"), sold=True)
        if qty < 1:
            qty = 1
        remaining_planned = max(show_item.quantity_planned - show_item.quantity_sold, 0)
        if remaining_planned and qty > remaining_planned:
            raise ValueError(f"Report row {row_index} sells {qty} of {sku}, exceeding show quantity remaining ({remaining_planned})")
        if qty > inventory.quantity_on_hand:
            raise ValueError(f"Report row {row_index} sells {qty} of {sku}, but only {inventory.quantity_on_hand} are on hand")

        external_order_id = _cell(row, header_map, "order_id")
        if not external_order_id:
            external_order_id = f"WN-{show.show_number}-{digest[:10]}-{row_index}"
        buyer = _cell(row, header_map, "buyer") or None
        sold_at = _parse_datetime(_cell(row, header_map, "sold_at"), show.scheduled_at or now)

        commission = _positive_cost(_cell(row, header_map, "commission_fee"))
        processing = _positive_cost(_cell(row, header_map, "processing_fee"))
        total_fees = _positive_cost(_cell(row, header_map, "total_fees"))
        if commission == 0 and processing == 0 and total_fees:
            commission = total_fees
        seller_shipping = _positive_cost(_cell(row, header_map, "seller_shipping"))
        fee_total = commission + processing + seller_shipping

        order = db.scalar(
            select(Order).where(Order.marketplace == "WHATNOT", Order.external_order_id == external_order_id)
        )
        if order is None:
            order = Order(
                marketplace="WHATNOT",
                external_order_id=external_order_id,
                buyer_handle=buyer,
                ordered_at=sold_at,
                currency="USD",
                order_total_cents=sale_price_cents * qty,
                tax_collected_cents=0,
                shipping_charged_cents=0,
                status=(_cell(row, header_map, "status") or "COMPLETE")[:30],
            )
            db.add(order)
            db.flush()

        existing_sale = db.scalar(
            select(Sale).where(
                Sale.order_id == order.order_id,
                Sale.show_item_id == show_item.show_item_id,
                Sale.inventory_id == inventory.inventory_id,
            )
        )
        if existing_sale is not None:
            continue

        gross = sale_price_cents * qty
        cost_basis = inventory.unit_cost_cents * qty
        sale = Sale(
            order_id=order.order_id,
            inventory_id=inventory.inventory_id,
            show_item_id=show_item.show_item_id,
            marketplace="WHATNOT",
            sold_at=sold_at,
            quantity=qty,
            unit_sale_price_cents=sale_price_cents,
            gross_item_cents=gross,
            cost_basis_cents=cost_basis,
            marketplace_fee_cents=commission,
            processing_fee_cents=processing,
            shipping_cost_allocated_cents=seller_shipping,
            packaging_cost_allocated_cents=0,
            discount_cents=0,
            refund_cents=0,
            other_cost_cents=0,
            currency="USD",
            notes=f"Imported from {show.show_number} Show Report",
        )
        db.add(sale)

        before_status = inventory.status
        inventory.quantity_on_hand -= qty
        show_item.quantity_sold += qty
        show_item.result_status = WhatnotResultStatus.SOLD.value
        if inventory.quantity_on_hand <= 0:
            inventory.quantity_on_hand = 0
            inventory.status = InventoryStatus.SOLD.value
        else:
            inventory.status = InventoryStatus.EBAY_QUEUE.value

        db.add(InventoryEvent(
            inventory_id=inventory.inventory_id,
            event_type="WHATNOT_SALE_RECONCILED",
            from_status=before_status,
            to_status=inventory.status,
            quantity_delta=-qty,
            marketplace="WHATNOT",
            reference_type="WHATNOT_SHOW",
            reference_id=show.show_id,
            message=f"Reconciled {qty} sold from {show.show_number}; order {external_order_id}",
        ))

        summary.sale_records += 1
        summary.sold_units += qty
        summary.gross_cents += gross
        summary.fee_cents += fee_total
        summary.cost_basis_cents += cost_basis
        summary.realized_profit_cents += gross - cost_basis - fee_total

    if unmatched_sold_rows:
        rows_text = ", ".join(str(n) for n in unmatched_sold_rows[:10])
        raise ValueError(
            "Sold rows could not be matched to this show's inventory (CSV row(s): " + rows_text + "). "
            "No reconciliation was applied. Ensure the report includes our exported SKU or description."
        )

    for show_item in show.items:
        inventory = show_item.inventory_item
        if show_item.quantity_sold == 0:
            show_item.result_status = WhatnotResultStatus.UNSOLD.value
            summary.unsold_items += 1
            if inventory.quantity_on_hand > 0:
                before_status = inventory.status
                inventory.status = InventoryStatus.EBAY_QUEUE.value
                if before_status != inventory.status:
                    db.add(InventoryEvent(
                        inventory_id=inventory.inventory_id,
                        event_type="WHATNOT_UNSOLD_TO_EBAY",
                        from_status=before_status,
                        to_status=inventory.status,
                        quantity_delta=0,
                        marketplace="WHATNOT",
                        reference_type="WHATNOT_SHOW",
                        reference_id=show.show_id,
                        message=f"Unsold in {show.show_number}; moved to EBAY_QUEUE",
                    ))
        elif inventory.quantity_on_hand > 0:
            inventory.status = InventoryStatus.EBAY_QUEUE.value

        if inventory.quantity_on_hand == 0:
            summary.sold_out_items += 1
        elif inventory.status == InventoryStatus.EBAY_QUEUE.value:
            summary.ebay_queue_items += 1

    show.status = WhatnotShowStatus.RECONCILED.value
    show.results_imported_at = now
    run.status = "COMPLETED"
    run.records_written = summary.sale_records
    run.completed_at = now
    db.flush()
    return summary
