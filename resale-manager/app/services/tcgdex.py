from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Card, InventoryItem, PriceSnapshot


TCGDEX_BASE_URL = "https://api.tcgdex.net/v2"


class TCGdexError(RuntimeError):
    pass


@dataclass(slots=True)
class PricingResult:
    inventory_id: int
    matched: bool
    source: str | None = None
    market_price_cents: int | None = None
    cardmarket_trend_cents: int | None = None
    currency: str | None = None
    message: str | None = None


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _local_number(card_number: str) -> str:
    value = (card_number or "").strip()
    if "/" in value:
        value = value.split("/", 1)[0]
    return value.lstrip("0") or "0"


def _language_code(language: str | None) -> str:
    mapping = {
        "EN": "en", "ENG": "en", "JA": "ja", "JP": "ja", "JPN": "ja",
        "FR": "fr", "DE": "de", "ES": "es", "IT": "it", "PT": "pt-br",
        "ZH-TW": "zh-tw", "ID": "id", "TH": "th",
    }
    return mapping.get((language or "EN").upper(), "en")


def _variant_keys(item: InventoryItem) -> list[str]:
    text = " ".join(filter(None, [item.finish, item.variant_label])).lower()
    if "reverse" in text:
        return ["reverse-holofoil", "reverse", "reverseHolofoil"]
    if "holo" in text or "foil" in text:
        return ["holofoil", "holo"]
    return ["normal"]


def _money_cents(value: Any) -> int | None:
    if value is None:
        return None
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    return int(round(amount * 100))


class TCGdexService:
    def __init__(self, client: httpx.Client | None = None, base_url: str = TCGDEX_BASE_URL):
        self.client = client or httpx.Client(timeout=12.0, headers={"User-Agent": "PokemonResaleManager/0.6"})
        self.base_url = base_url.rstrip("/")
        self._sets_cache: dict[str, list[dict[str, Any]]] = {}
        self._card_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    def _get_json(self, path: str) -> Any:
        try:
            response = self.client.get(f"{self.base_url}{path}")
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TCGdexError(str(exc)) from exc

    def _sets(self, language: str) -> list[dict[str, Any]]:
        if language not in self._sets_cache:
            data = self._get_json(f"/{language}/sets")
            if not isinstance(data, list):
                raise TCGdexError("TCGdex returned an unexpected sets response")
            self._sets_cache[language] = data
        return self._sets_cache[language]

    def _match_set_id(self, card: Card, language: str) -> str | None:
        card_set = card.card_set
        if card_set is None:
            return None
        candidates = self._sets(language)
        wanted_name = _norm(card_set.name)
        wanted_code = _norm(card_set.set_code)
        wanted_external = _norm(card_set.external_set_id)
        for candidate in candidates:
            cid = str(candidate.get("id") or "")
            cname = str(candidate.get("name") or "")
            if wanted_external and _norm(cid) == wanted_external:
                return cid
            if wanted_name and _norm(cname) == wanted_name:
                return cid
            if wanted_code and _norm(cid) == wanted_code:
                return cid
        return None

    def fetch_card(self, card: Card, language: str) -> dict[str, Any] | None:
        lang = _language_code(language)
        set_id = self._match_set_id(card, lang)
        if not set_id:
            return None
        local_id = _local_number(card.card_number)
        key = (lang, set_id, local_id)
        if key not in self._card_cache:
            try:
                data = self._get_json(f"/{lang}/sets/{set_id}/{local_id}")
            except TCGdexError:
                return None
            if not isinstance(data, dict):
                return None
            self._card_cache[key] = data
        data = self._card_cache[key]
        if _norm(str(data.get("name") or "")) != _norm(card.name):
            return None
        return data

    def refresh_item(self, db: Session, item: InventoryItem) -> PricingResult:
        if item.card is None:
            return PricingResult(item.inventory_id, False, message="No catalog card is linked")

        data = self.fetch_card(item.card, item.language)
        if not data:
            return PricingResult(item.inventory_id, False, message="No confident TCGdex set/card match")

        pricing = data.get("pricing") or {}
        tcgplayer = pricing.get("tcgplayer") or {}
        selected_variant = None
        selected_prices: dict[str, Any] | None = None
        for key in _variant_keys(item):
            value = tcgplayer.get(key)
            if isinstance(value, dict):
                selected_variant = key
                selected_prices = value
                break

        now = datetime.now(timezone.utc)
        market_cents = None
        source = None
        if selected_prices is not None:
            market_cents = _money_cents(selected_prices.get("marketPrice"))
            low_cents = _money_cents(selected_prices.get("lowPrice"))
            high_cents = _money_cents(selected_prices.get("highPrice"))
            if market_cents is not None:
                source = f"TCGDEX:TCGPLAYER:{selected_variant}"
                db.add(PriceSnapshot(
                    card_id=item.card.card_id,
                    source=source,
                    condition=item.condition,
                    finish=item.finish or item.variant_label,
                    language=item.language,
                    market_price_cents=market_cents,
                    low_price_cents=low_cents,
                    high_price_cents=high_cents,
                    currency=str(tcgplayer.get("unit") or "USD").upper(),
                    captured_at=now,
                ))
                item.market_value_cents = market_cents
                item.market_value_source = source
                item.market_value_updated_at = now

        cardmarket = pricing.get("cardmarket") or {}
        trend_value = cardmarket.get("trend")
        text = " ".join(filter(None, [item.finish, item.variant_label])).lower()
        if "holo" in text and cardmarket.get("trend-holo") is not None:
            trend_value = cardmarket.get("trend-holo")
        cardmarket_cents = _money_cents(trend_value)
        if cardmarket_cents is not None:
            db.add(PriceSnapshot(
                card_id=item.card.card_id,
                source="TCGDEX:CARDMARKET:TREND",
                condition=item.condition,
                finish=item.finish or item.variant_label,
                language=item.language,
                market_price_cents=cardmarket_cents,
                currency=str(cardmarket.get("unit") or "EUR").upper(),
                captured_at=now,
            ))

        if market_cents is None and cardmarket_cents is None:
            return PricingResult(item.inventory_id, True, message="Card matched, but no marketplace price was available")
        return PricingResult(
            item.inventory_id, True, source=source, market_price_cents=market_cents,
            cardmarket_trend_cents=cardmarket_cents,
            currency=str(tcgplayer.get("unit") or "USD").upper() if market_cents is not None else None,
        )

    def refresh_inventory(self, db: Session, items: Iterable[InventoryItem] | None = None) -> dict[str, Any]:
        if items is None:
            items = db.scalars(
                select(InventoryItem)
                .where(InventoryItem.quantity_on_hand > 0, InventoryItem.card_id.is_not(None))
                .options(joinedload(InventoryItem.card).joinedload(Card.card_set))
                .order_by(InventoryItem.inventory_id)
            ).all()

        results: list[PricingResult] = []
        for item in items:
            try:
                results.append(self.refresh_item(db, item))
            except TCGdexError as exc:
                results.append(PricingResult(item.inventory_id, False, message=str(exc)))

        priced = sum(1 for result in results if result.market_price_cents is not None)
        matched = sum(1 for result in results if result.matched)
        db.flush()
        return {
            "checked": len(results),
            "matched": matched,
            "priced": priced,
            "unmatched": len(results) - matched,
            "results": results,
        }
