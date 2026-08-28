from __future__ import annotations

import sys
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine

EXPECTED_TABLES = {
    "app_settings",
    "business_expenses",
    "card_sets",
    "cards",
    "integration_runs",
    "inventory_events",
    "inventory_images",
    "inventory_items",
    "listing_items",
    "listings",
    "orders",
    "price_snapshots",
    "purchases",
    "sales",
    "shipments",
    "storage_locations",
    "whatnot_show_items",
    "whatnot_shows",
}


def main() -> int:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    missing = sorted(EXPECTED_TABLES - tables)
    extra = sorted(tables - EXPECTED_TABLES - {"alembic_version"})

    print(f"Database: {settings.resolved_database_url}")
    print(f"Business tables found: {len(EXPECTED_TABLES & tables)}/{len(EXPECTED_TABLES)}")

    if missing:
        print("Missing tables:")
        for name in missing:
            print(f"  - {name}")
        return 1

    if "alembic_version" not in tables:
        print("Missing alembic_version table")
        return 1

    with engine.connect() as connection:
        version = connection.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar_one_or_none()
    print(f"Alembic revision: {version or 'unknown'}")
    if extra:
        print("Additional tables:")
        for name in extra:
            print(f"  - {name}")

    print("Database verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
