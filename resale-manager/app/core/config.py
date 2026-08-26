from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
load_dotenv(PROJECT_ROOT / ".env", override=False)


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("PRM_APP_NAME", "Pokemon Resale Manager")
    environment: str = os.getenv("PRM_ENV", "development")
    host: str = os.getenv("PRM_HOST", "127.0.0.1")
    port: int = int(os.getenv("PRM_PORT", "8000"))
    data_dir: Path = Path(os.getenv("PRM_DATA_DIR", str(DEFAULT_DATA_DIR)))
    database_url: str = os.getenv("DATABASE_URL", "")

    # eBay OAuth / Sell APIs. EBAY_REDIRECT_URI is retained as a compatibility
    # alias for eBay's OAuth Redirect URL name (RuName).
    ebay_environment: str = os.getenv("EBAY_ENVIRONMENT", "sandbox").strip().lower()
    ebay_client_id: str = os.getenv("EBAY_CLIENT_ID", "").strip()
    ebay_client_secret: str = os.getenv("EBAY_CLIENT_SECRET", "").strip()
    ebay_runame: str = os.getenv("EBAY_RUNAME", os.getenv("EBAY_REDIRECT_URI", "")).strip()
    ebay_marketplace_id: str = os.getenv("EBAY_MARKETPLACE_ID", "EBAY_US").strip().upper()
    ebay_locale: str = os.getenv("EBAY_LOCALE", "en-US").strip()
    ebay_default_category_id: str = os.getenv("EBAY_DEFAULT_CATEGORY_ID", "183454").strip()

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.data_dir / "pokemon_resale_manager.db"
        return f"sqlite:///{db_path.as_posix()}"

    @property
    def ebay_configured(self) -> bool:
        return bool(self.ebay_client_id and self.ebay_client_secret and self.ebay_runame)

    @property
    def ebay_is_sandbox(self) -> bool:
        return self.ebay_environment != "production"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
