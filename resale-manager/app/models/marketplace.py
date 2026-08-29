from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, utcnow

class WhatnotShow(Base):
    __tablename__ = "whatnot_shows"

    show_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    theme: Mapped[Optional[str]] = mapped_column(String(200))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    export_generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    results_imported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    items: Mapped[list["WhatnotShowItem"]] = relationship(back_populates="show", cascade="all, delete-orphan")

class WhatnotShowItem(Base):
    __tablename__ = "whatnot_show_items"

    show_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("whatnot_shows.show_id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.inventory_id"), nullable=False, index=True)
    sequence_number: Mapped[Optional[int]] = mapped_column(Integer)
    quantity_planned: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title_override: Mapped[Optional[str]] = mapped_column(String(250))
    auction_start_cents: Mapped[Optional[int]] = mapped_column(Integer)
    sale_format: Mapped[str] = mapped_column(String(30), default="AUCTION", nullable=False)
    export_row_number: Mapped[Optional[int]] = mapped_column(Integer)
    external_product_id: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    result_status: Mapped[str] = mapped_column(String(30), default="QUEUED", nullable=False, index=True)
    quantity_sold: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    show: Mapped["WhatnotShow"] = relationship(back_populates="items")
    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="show_items")
    sales: Mapped[list["Sale"]] = relationship(back_populates="show_item")

    __table_args__ = (
        UniqueConstraint("show_id", "inventory_id", name="uq_show_inventory"),
        CheckConstraint("quantity_planned > 0", name="qty_planned_positive"),
        CheckConstraint("quantity_sold >= 0", name="qty_sold_nonnegative"),
        CheckConstraint("auction_start_cents IS NULL OR auction_start_cents >= 0", name="auction_start_nonnegative"),
    )

class Listing(TimestampMixin, Base):
    __tablename__ = "listings"

    listing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    marketplace: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    external_listing_id: Mapped[Optional[str]] = mapped_column(String(160), index=True)
    external_offer_id: Mapped[Optional[str]] = mapped_column(String(160), index=True)
    listing_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    minimum_offer_cents: Mapped[Optional[int]] = mapped_column(Integer)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)
    listing_url: Mapped[Optional[str]] = mapped_column(Text)
    listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    items: Mapped[list["ListingItem"]] = relationship(back_populates="listing", cascade="all, delete-orphan")
    sales: Mapped[list["Sale"]] = relationship(back_populates="listing")

    __table_args__ = (
        UniqueConstraint("marketplace", "external_listing_id", name="uq_listing_marketplace_external"),
        CheckConstraint("price_cents >= 0", name="price_nonnegative"),
        CheckConstraint("minimum_offer_cents IS NULL OR minimum_offer_cents >= 0", name="minimum_offer_nonnegative"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )

class ListingItem(Base):
    __tablename__ = "listing_items"

    listing_item_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.listing_id", ondelete="CASCADE"), nullable=False, index=True)
    inventory_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.inventory_id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    listing: Mapped["Listing"] = relationship(back_populates="items")
    inventory_item: Mapped["InventoryItem"] = relationship(back_populates="listing_items")

    __table_args__ = (
        UniqueConstraint("listing_id", "inventory_id", name="uq_listing_inventory"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
    )
