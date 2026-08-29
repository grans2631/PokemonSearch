from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import InventoryEvent, InventoryImage
from app.services.ebay import EbayError
from app.services.ebay_v06 import EbayV06Service


APPLICATION_SCOPE = "https://api.ebay.com/oauth/api_scope"


class EbayV06RuntimeService(EbayV06Service):
    """Runtime corrections for eBay metadata/media APIs that use application OAuth."""

    @property
    def media_base(self) -> str:
        return "https://apim.sandbox.ebay.com" if settings.ebay_is_sandbox else "https://apim.ebay.com"

    def _application_access_token(self) -> str:
        self._require_config()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_base}/identity/v1/oauth2/token",
                    auth=(settings.ebay_client_id, settings.ebay_client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={"grant_type": "client_credentials", "scope": APPLICATION_SCOPE},
                )
        except httpx.HTTPError as exc:
            raise EbayError(f"eBay application OAuth request failed: {exc}") from exc
        if response.status_code >= 400:
            raise EbayError(self._error_text(response, prefix="eBay application OAuth error"))
        payload = response.json()
        token = str(payload.get("access_token") or "")
        if not token:
            raise EbayError("eBay application OAuth did not return an access token")
        return token

    def _application_request(self, method: str, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._application_access_token()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.request(
                    method,
                    f"{self.api_base}{path}",
                    params=params,
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                )
        except httpx.HTTPError as exc:
            raise EbayError(f"eBay metadata request failed: {exc}") from exc
        if response.status_code >= 400:
            raise EbayError(self._error_text(response, prefix="eBay metadata API error"))
        return response.json() if response.content else {}

    def upload_image_to_ebay(self, db: Session, *, image_id: int) -> InventoryImage:
        image = db.get(InventoryImage, image_id)
        if image is None:
            raise EbayError("Inventory image not found")
        if image.external_url and image.external_url.startswith("https://"):
            return image
        if not image.local_path:
            raise EbayError("This image has no local file to upload")
        path = Path(image.local_path)
        if not path.exists() or not path.is_file():
            raise EbayError("Local image file is missing")

        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        token = self._application_access_token()
        try:
            with httpx.Client(timeout=max(self.timeout, 60.0)) as client:
                with path.open("rb") as fh:
                    response = client.post(
                        f"{self.media_base}/commerce/media/v1_beta/image/create_image_from_file",
                        headers={"Authorization": f"Bearer {token}"},
                        files={"image": (path.name, fh, content_type)},
                    )
        except httpx.HTTPError as exc:
            raise EbayError(f"eBay Media upload failed: {exc}") from exc
        if response.status_code >= 400:
            raise EbayError(self._error_text(response, prefix="eBay Media API error"))
        payload = response.json()
        image_url = str(payload.get("imageUrl") or "")
        if not image_url.startswith("https://"):
            raise EbayError("eBay Media API did not return an EPS image URL")
        image.external_url = image_url
        db.add(InventoryEvent(
            inventory_id=image.inventory_id,
            event_type="IMAGE_UPLOADED_EBAY",
            marketplace="EBAY",
            reference_type="INVENTORY_IMAGE",
            reference_id=image.image_id,
            quantity_delta=0,
            message="Uploaded inventory image to eBay Picture Services",
        ))
        db.flush()
        return image

    def get_default_category_tree_id(self) -> str:
        payload = self._application_request(
            "GET",
            "/commerce/taxonomy/v1/get_default_category_tree_id",
            params={"marketplace_id": settings.ebay_marketplace_id},
        )
        tree_id = str(payload.get("categoryTreeId") or "")
        if not tree_id:
            raise EbayError("eBay Taxonomy API did not return a category tree ID")
        return tree_id

    def suggest_categories(self, query_text: str) -> list[dict[str, Any]]:
        tree_id = self.get_default_category_tree_id()
        payload = self._application_request(
            "GET",
            f"/commerce/taxonomy/v1_beta/category_tree/{quote(tree_id, safe='')}/get_category_suggestions",
            params={"q": query_text[:350]},
        )
        return payload.get("categorySuggestions", [])

    def get_category_aspects(self, category_id: str) -> tuple[str, list[dict[str, Any]]]:
        tree_id = self.get_default_category_tree_id()
        payload = self._application_request(
            "GET",
            f"/commerce/taxonomy/v1_beta/category_tree/{quote(tree_id, safe='')}/get_item_aspects_for_category",
            params={"category_id": category_id},
        )
        return tree_id, payload.get("aspects", [])
