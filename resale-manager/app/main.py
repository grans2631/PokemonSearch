from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.core.config import settings
from app.routes import api, web


APP_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="Pokemon card acquisition, inventory, Whatnot-to-eBay workflow, and profit tracking.",
)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")
app.include_router(web.router)
app.include_router(api.router)
