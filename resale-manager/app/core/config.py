from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


@dataclass(frozen=True, slots=True)
class Settings:
    app_name: str = os.getenv("PRM_APP_NAME", "Pokemon Resale Manager")
    environment: str = os.getenv("PRM_ENV", "development")
    host: str = os.getenv("PRM_HOST", "127.0.0.1")
    port: int = int(os.getenv("PRM_PORT", "8000"))
    data_dir: Path = Path(os.getenv("PRM_DATA_DIR", str(DEFAULT_DATA_DIR)))
    database_url: str = os.getenv("DATABASE_URL", "")

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        db_path = self.data_dir / "pokemon_resale_manager.db"
        return f"sqlite:///{db_path.as_posix()}"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
