from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, utcnow

class Shipment(Base):
    __tablename__ = "shipments"

    shipment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    external_shipment_id: Mapped[Optional[str]] = mapped_column(String(160), index=True)
    buyer_handle: Mapped[Optional[str]] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    carrier: Mapped[Optional[str]] = mapped_column(String(80))
    service: Mapped[Optional[str]] = mapped_column(String(120))
    tracking_number: Mapped[Optional[str]] = mapped_column(String(160), index=True)
    weight_grams: Mapped[Optional[int]] = mapped_column(Integer)
    postage_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    packaging_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    label_source: Mapped[Optional[str]] = mapped_column(String(80))
    label_path: Mapped[Optional[str]] = mapped_column(Text)
    packed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    shipped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="shipment")

    __table_args__ = (
        CheckConstraint("weight_grams IS NULL OR weight_grams >= 0", name="weight_nonnegative"),
        CheckConstraint("postage_cost_cents >= 0", name="postage_nonnegative"),
        CheckConstraint("packaging_cost_cents >= 0", name="packaging_nonnegative"),
    )

class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    order_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shipment_id: Mapped[Optional[int]] = mapped_column(ForeignKey("shipments.shipment_id"), index=True)
    marketplace: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    external_order_id: Mapped[str] = mapped_column(String(160), nullable=False)
    buyer_handle: Mapped[Optional[str]] = mapped_column(String(160))
    ordered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    order_total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_collected_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shipping_charged_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    shipment: Mapped[Optional["Shipment"]] = relationship(back_populates="orders")
    sales: Mapped[list["Sale"]] = relationship(back_populates="order")
    expenses: Mapped[list["BusinessExpense"]] = relationship(back_populates="order")

    __table_args__ = (
        UniqueConstraint("marketplace", "external_order_id", name="uq_order_marketplace_external"),
        CheckConstraint("order_total_cents >= 0", name="order_total_nonnegative"),
        CheckConstraint("tax_collected_cents >= 0", name="tax_nonnegative"),
        CheckConstraint("shipping_charged_cents >= 0", name="shipping_charged_nonnegative"),
    )

class Sale(Base):
    __tablename__ = "sales"

    sale_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.order_id"), index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.inventory_id"), nullable=False, index=True)
    listing_id: Mapped[Optional[int]] = mapped_column(ForeignKey("listings.listing_id"), index=True)
    show_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("whatnot_show_items.show_item_id"), index=True)
    marketplace: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_sale_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    gross_item_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    cost_basis_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    marketplace_fee_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_fee_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shipping_cost_allocated_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    packaging_cost_allocated_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    refund_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    other_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    order: Mapped[Optional["Order"]] = relationship(back_populates="sales")
    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="sales")
    listing: Mapped[Optional["Listing"]] = relationship(back_populates="sales")
    show_item: Mapped[Optional["WhatnotShowItem"]] = relationship(back_populates="sales")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_sale_price_cents >= 0", name="unit_sale_nonnegative"),
        CheckConstraint("gross_item_cents >= 0", name="gross_nonnegative"),
        CheckConstraint("cost_basis_cents >= 0", name="cost_basis_nonnegative"),
        CheckConstraint("marketplace_fee_cents >= 0", name="marketplace_fee_nonnegative"),
        CheckConstraint("processing_fee_cents >= 0", name="processing_fee_nonnegative"),
        CheckConstraint("shipping_cost_allocated_cents >= 0", name="shipping_allocated_nonnegative"),
        CheckConstraint("packaging_cost_allocated_cents >= 0", name="packaging_allocated_nonnegative"),
        CheckConstraint("discount_cents >= 0", name="discount_nonnegative"),
        CheckConstraint("refund_cents >= 0", name="refund_nonnegative"),
        CheckConstraint("other_cost_cents >= 0", name="other_cost_nonnegative"),
    )

    @property
    def realized_profit_cents(self) -> int:
        return (
            self.gross_item_cents
            - self.cost_basis_cents
            - self.marketplace_fee_cents
            - self.processing_fee_cents
            - self.shipping_cost_allocated_cents
            - self.packaging_cost_allocated_cents
            - self.discount_cents
            - self.refund_cents
            - self.other_cost_cents
        )

class BusinessExpense(Base):
    __tablename__ = "business_expenses"

    expense_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(250), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    marketplace: Mapped[Optional[str]] = mapped_column(String(30))
    purchase_id: Mapped[Optional[int]] = mapped_column(ForeignKey("purchases.purchase_id"), index=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.order_id"), index=True)
    receipt_path: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    purchase: Mapped[Optional["Purchase"]] = relationship(back_populates="expenses")
    order: Mapped[Optional["Order"]] = relationship(back_populates="expenses")

    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="amount_nonnegative"),
    )
