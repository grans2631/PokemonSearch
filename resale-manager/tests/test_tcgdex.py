from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import PriceSnapshot
from app.services.intake import create_inventory_item, create_purchase, find_or_create_card
from app.services.tcgdex import TCGdexService


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeClient:
    def get(self, url):
        if url.endswith("/en/sets"):
            return FakeResponse([
                {"id": "sv06", "name": "Twilight Masquerade"},
            ])
        if url.endswith("/en/sets/sv06/167"):
            return FakeResponse({
                "id": "sv06-167",
                "localId": "167",
                "name": "Ogerpon ex",
                "pricing": {
                    "tcgplayer": {
                        "unit": "USD",
                        "normal": {
                            "lowPrice": 10.00,
                            "marketPrice": 12.34,
                            "highPrice": 15.00,
                        },
                    },
                    "cardmarket": {
                        "unit": "EUR",
                        "trend": 11.11,
                    },
                },
            })
        raise AssertionError(f"Unexpected URL: {url}")


def test_refresh_item_updates_inventory_and_price_history():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        purchase = create_purchase(db, purchase_date=date(2026, 8, 28), source_type="PACK_OPENED", subtotal_cents=0)
        card = find_or_create_card(
            db,
            set_code="TWM",
            set_name="Twilight Masquerade",
            card_name="Ogerpon ex",
            card_number="167/167",
            rarity="Double Rare",
        )
        item = create_inventory_item(
            db,
            purchase=purchase,
            card=card,
            location_id=None,
            condition="NM",
            finish="normal",
            unit_cost_cents=0,
        )
        db.flush()

        result = TCGdexService(client=FakeClient()).refresh_item(db, item)
        db.flush()

        assert result.matched is True
        assert result.market_price_cents == 1234
        assert item.market_value_cents == 1234
        assert item.market_value_source == "TCGDEX:TCGPLAYER:normal"

        snapshots = db.query(PriceSnapshot).order_by(PriceSnapshot.price_id).all()
        assert len(snapshots) == 2
        assert snapshots[0].currency == "USD"
        assert snapshots[0].market_price_cents == 1234
        assert snapshots[1].currency == "EUR"
        assert snapshots[1].market_price_cents == 1111
