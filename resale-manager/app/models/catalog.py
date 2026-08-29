from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, utcnow

class CardSet(TimestampMixin, Base):
    __tablename__ = "card_sets"

    set_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    set_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    series_name: Mapped[Optional[str]] = mapped_column(String(200))
    language: Mapped[str] = mapped_column(String(8), default="EN", nullable=False)
    release_date: Mapped[Optional[date]] = mapped_column(Date)
    printed_total: Mapped[Optional[int]] = mapped_column(Integer)
    actual_total: Mapped[Optional[int]] = mapped_column(Integer)
    tcgplayer_set_id: Mapped[Optional[str]] = mapped_column(String(100))
    external_set_id: Mapped[Optional[str]] = mapped_column(String(100))

    cards: Mapped[list["Card"]] = relationship(back_populates="card_set")

    __table_args__ = (
        UniqueConstraint("set_code", "language", name="uq_card_sets_code_language"),
        CheckConstraint("printed_total IS NULL OR printed_total >= 0", name="printed_total_nonnegative"),
        CheckConstraint("actual_total IS NULL OR actual_total >= 0", name="actual_total_nonnegative"),
    )

class Card(TimestampMixin, Base):
    __tablename__ = "cards"

    card_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("card_sets.set_id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    card_number: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rarity: Mapped[Optional[str]] = mapped_column(String(80), index=True)
    card_type: Mapped[Optional[str]] = mapped_column(String(80))
    pokemon_name: Mapped[Optional[str]] = mapped_column(String(120), index=True)
    tcgplayer_product_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    external_card_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    image_url_small: Mapped[Optional[str]] = mapped_column(Text)
    image_url_large: Mapped[Optional[str]] = mapped_column(Text)

    card_set: Mapped["CardSet"] = relationship(back_populates="cards")
    inventory_items: Mapped[list["InventoryItem"]] = relationship(back_populates="card")
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(back_populates="card")

    __table_args__ = (
        UniqueConstraint("set_id", "card_number", "name", name="uq_cards_set_number_name"),
    )

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    price_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.card_id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    condition: Mapped[Optional[str]] = mapped_column(String(20))
    finish: Mapped[Optional[str]] = mapped_column(String(80))
    language: Mapped[Optional[str]] = mapped_column(String(8))
    grading_company: Mapped[Optional[str]] = mapped_column(String(40))
    grade: Mapped[Optional[str]] = mapped_column(String(20))
    market_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    low_price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    high_price_cents: Mapped[Optional[int]] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    card: Mapped["Card"] = relationship(back_populates="price_snapshots")

    __table_args__ = (
        CheckConstraint("market_price_cents >= 0", name="market_price_nonnegative"),
        CheckConstraint("low_price_cents IS NULL OR low_price_cents >= 0", name="low_price_nonnegative"),
        CheckConstraint("high_price_cents IS NULL OR high_price_cents >= 0", name="high_price_nonnegative"),
    )
