from datetime import datetime, timezone

from app.models import Sale


def test_sale_profit_calculation():
    sale = Sale(
        inventory_id=1,
        marketplace="EBAY",
        sold_at=datetime.now(timezone.utc),
        quantity=1,
        unit_sale_price_cents=8000,
        gross_item_cents=8000,
        cost_basis_cents=4000,
        marketplace_fee_cents=1000,
        processing_fee_cents=0,
        shipping_cost_allocated_cents=500,
        packaging_cost_allocated_cents=100,
        discount_cents=0,
        refund_cents=0,
        other_cost_cents=0,
    )
    assert sale.realized_profit_cents == 2400
