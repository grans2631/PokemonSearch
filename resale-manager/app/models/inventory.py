from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, utcnow

class Purchase(TimestampMixin, Base):
    __tablename__ = "purchases"

    purchase_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(200))
    external_order_id: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sales_tax_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shipping_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    buyer_fees_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    landed_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    allocation_status: Mapped[str] = mapped_column(String(20), default="UNALLOCATED", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="purchase")
    expenses: Mapped[list["BusinessExpense"]] = relationship(back_populates="purchase")

    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="subtotal_nonnegative"),
        CheckConstraint("sales_tax_cents >= 0", name="sales_tax_nonnegative"),
        CheckConstraint("shipping_cents >= 0", name="shipping_nonnegative"),
        CheckConstraint("buyer_fees_cents >= 0", name="buyer_fees_nonnegative"),
        CheckConstraint("discount_cents >= 0", name="discount_nonnegative"),
        CheckConstraint("landed_cost_cents >= 0", name="landed_cost_nonnegative"),
    )

class StorageLocation(Base):
    __tablename__ = "storage_locations"

    location_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    location_code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    location_type: Mapped[str] = mapped_column(String(40), nullable=False)
    parent_location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("storage_locations.location_id"))
    active: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    parent: Mapped[Optional["StorageLocation"]] = relationship(remote_side=[location_id], back_populates="children")
    children: Mapped[list["StorageLocation"]] = relationship(back_populates="parent")
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="location")

    __table_args__ = (
        CheckConstraint("active IN (0, 1)", name="active_boolean"),
    )

class InventoryItem(TimestampMixin, Base):
    __tablename__ = "inventory_items"

    inventory_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cards.card_id"), index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.purchase_id"), nullable=False, index=True)
    location_id: Mapped[Optional[int]] = mapped_column(ForeignKey("storage_locations.location_id"), index=True)
    inventory_type: Mapped[str] = mapped_column(String(40), default="SINGLE_CARD", nullable=False)
    tracking_mode: Mapped[str] = mapped_column(String(20), default="SERIALIZED", nullable=False)
    condition: Mapped[Optional[str]] = mapped_column(String(20), index=True)
    language: Mapped[str] = mapped_column(String(8), default="EN", nullable=False)
    finish: Mapped[Optional[str]] = mapped_column(String(80))
    variant_label: Mapped[Optional[str]] = mapped_column(String(120))
    is_graded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    grading_company: Mapped[Optional[str]] = mapped_column(String(40))
    grade: Mapped[Optional[str]] = mapped_column(String(20))
    cert_number: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    quantity_received: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    quantity_on_hand: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    market_value_cents: Mapped[Optional[int]] = mapped_column(Integer)
    market_value_source: Mapped[Optional[str]] = mapped_column(String(80))
    market_value_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    target_price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    minimum_price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED", nullable=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    card: Mapped[Optional["Card"]] = relationship(back_populates="inventory_items")
    purchase: Mapped["Purchase"] = relationship(back_populates="inventory_items")
    location: Mapped[Optional["StorageLocation"]] = relationship(back_populates="inventory_items")
    images: Mapped[list["InventoryImage"]] = relationship(back_populates="inventory_item", cascade="all, delete-orphan")
    events: Mapped[list["InventoryEvent"]] = relationship(back_populates="inventory_item", cascade="all, delete-orphan")
    show_items: Mapped[list["WhatnotShowItem"]] = relationship(back_populates="inventory_item")
    listing_items: Mapped[list["ListingItem"]] = relationship(back_populates="inventory_item")
    sales: Mapped[list["Sale"]] = relationship(back_populates="inventory_item")

    __table_args__ = (
        CheckConstraint("is_graded IN (0, 1)", name="is_graded_boolean"),
        CheckConstraint("quantity_received >= 0", name="qty_received_nonnegative"),
        CheckConstraint("quantity_on_hand >= 0", name="qty_on_hand_nonnegative"),
        CheckConstraint("unit_cost_cents >= 0", name="unit_cost_nonnegative"),
        CheckConstraint("market_value_cents IS NULL OR market_value_cents >= 0", name="market_nonnegative"),
        CheckConstraint("target_price_cents IS NULL OR target_price_cents >= 0", name="target_nonnegative"),
        CheckConstraint("minimum_price_cents IS NULL OR minimum_price_cents >= 0", name="minimum_nonnegative"),
        Index("ix_inventory_status_location", "status", "location_id"),
    )

class InventoryImage(Base):
    __tablename__ = "inventory_images"

    image_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.inventory_id", ondelete="CASCADE"), nullable=False, index=True)
    image_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_primary: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    local_path: Mapped[Optional[str]] = mapped_column(Text)
    external_url: Mapped[Optional[str]] = mapped_column(Text)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    image_type: Mapped[Optional[str]] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="images")

    __table_args__ = (
        CheckConstraint("is_primary IN (0, 1)", name="is_primary_boolean"),
        CheckConstraint("image_order >= 0", name="image_order_nonnegative"),
    )

class InventoryEvent(Base):
    __tablename__ = "inventory_events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.inventory_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    from_status: Mapped[Optional[str]] = mapped_column(String(30))
    to_status: Mapped[Optional[str]] = mapped_column(String(30))
    quantity_delta: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    marketplace: Mapped[Optional[str]] = mapped_column(String(30))
    reference_type: Mapped[Optional[str]] = mapped_column(String(50))
    reference_id: Mapped[Optional[int]] = mapped_column(Integer)
    message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="events")
