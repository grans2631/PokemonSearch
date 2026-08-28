from __future__ import annotations

import hashlib
import mimetypes
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import InventoryStatus
from app.models import AppSetting, InventoryEvent, InventoryImage, InventoryItem, Listing
from app.models.base import utcnow
from app.services.ebay import EbayError, EbayService


APPROVAL_PREFIX = "ebay.listing."
MAX_IMAGE_BYTES = 15 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


@dataclass(slots=True)
class TaxonomyValidation:
    category_id: str
    category_tree_id: str
    required_aspects: list[str]
    recommended_aspects: list[str]
    missing_required_aspects: list[str]
    supplied_aspects: dict[str, list[str]]


class EbayV06Service(EbayService):
    """v0.6 eBay layer: image upload, taxonomy checks, approval, Sandbox publish/withdraw."""

    def _approval_key(self, listing_id: int) -> str:
        return f"{APPROVAL_PREFIX}{listing_id}.approved"

    def is_approved(self, db: Session, listing_id: int) -> bool:
        return self.get_setting(db, self._approval_key(listing_id)).lower() == "true"

    def set_approved(self, db: Session, listing_id: int, approved: bool) -> None:
        self.set_setting(db, self._approval_key(listing_id), "true" if approved else "false")
        self.set_setting(db, f"{APPROVAL_PREFIX}{listing_id}.approved_at", utcnow().isoformat() if approved else "")

    def store_local_image(
        self,
        db: Session,
        *,
        inventory: InventoryItem,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> InventoryImage:
        if not content:
            raise EbayError("Image upload is empty")
        if len(content) > MAX_IMAGE_BYTES:
            raise EbayError("Image exceeds the 15 MB application upload limit")
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise EbayError("Only JPEG and PNG images are accepted in v0.6")

        suffix = ALLOWED_IMAGE_TYPES[content_type]
        image_root = settings.data_dir / "images" / inventory.sku
        image_root.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(content).hexdigest()
        safe_name = f"{secrets.token_hex(8)}{suffix}"
        path = image_root / safe_name
        path.write_bytes(content)

        image_order = (db.scalar(
            select(func.max(InventoryImage.image_order)).where(InventoryImage.inventory_id == inventory.inventory_id)
        ) or 0) + 1
        image = InventoryImage(
            inventory_id=inventory.inventory_id,
            image_order=image_order,
            is_primary=1 if image_order == 1 else 0,
            local_path=str(path),
            external_url=None,
            sha256=digest,
            image_type="FRONT" if image_order == 1 else "DETAIL",
        )
        db.add(image)
        db.flush()
        db.add(InventoryEvent(
            inventory_id=inventory.inventory_id,
            event_type="IMAGE_ADDED",
            from_status=inventory.status,
            to_status=inventory.status,
            quantity_delta=0,
            marketplace="EBAY",
            reference_type="INVENTORY_IMAGE",
            reference_id=image.image_id,
            message=f"Stored local inventory image {Path(filename).name[:120]}",
        ))
        db.flush()
        return image

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
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise EbayError("Only JPEG and PNG files can be sent to eBay in v0.6")

        token = self._access_token()
        endpoint = f"{self.api_base}/commerce/media/v1_beta/image/create_image_from_file"
        for attempt in range(2):
            try:
                with httpx.Client(timeout=max(self.timeout, 60.0)) as client:
                    with path.open("rb") as fh:
                        response = client.post(
                            endpoint,
                            headers={"Authorization": f"Bearer {token}"},
                            files={"image": (path.name, fh, content_type)},
                        )
            except httpx.HTTPError as exc:
                raise EbayError(f"eBay Media upload failed: {exc}") from exc
            if response.status_code == 401 and attempt == 0:
                token = self._access_token(force_refresh=True)
                continue
            if response.status_code >= 400:
                raise EbayError(self._error_text(response, prefix="eBay Media API error"))
            try:
                payload = response.json()
            except ValueError as exc:
                raise EbayError("eBay Media API returned a non-JSON response") from exc
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
        raise EbayError("eBay Media upload failed after token refresh")

    def get_default_category_tree_id(self) -> str:
        payload = self.request(
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
        payload = self.request(
            "GET",
            f"/commerce/taxonomy/v1_beta/category_tree/{quote(tree_id, safe='')}/get_category_suggestions",
            params={"q": query_text[:350]},
        )
        return payload.get("categorySuggestions", [])

    def get_category_aspects(self, category_id: str) -> tuple[str, list[dict[str, Any]]]:
        tree_id = self.get_default_category_tree_id()
        payload = self.request(
            "GET",
            f"/commerce/taxonomy/v1/category_tree/{quote(tree_id, safe='')}/get_item_aspects_for_category",
            params={"category_id": category_id},
        )
        return tree_id, payload.get("aspects", [])

    def validate_taxonomy(self, db: Session, *, listing_id: int) -> TaxonomyValidation:
        listing, inventory = self._load_listing_inventory(db, listing_id)
        category_id = self.get_setting(db, f"ebay.listing.{listing.listing_id}.category_id") or self.listing_settings(db)["category_id"]
        if not category_id:
            raise EbayError("No eBay category ID is selected for this listing")
        tree_id, aspects = self.get_category_aspects(category_id)
        supplied = self._product_aspects(inventory)
        supplied_names = {name.casefold() for name in supplied}
        required: list[str] = []
        recommended: list[str] = []
        for aspect in aspects:
            name = str(aspect.get("localizedAspectName") or "").strip()
            if not name:
                continue
            constraint = aspect.get("aspectConstraint") or {}
            if constraint.get("aspectRequired") is True:
                required.append(name)
            elif str(constraint.get("aspectUsage") or "").upper() == "RECOMMENDED":
                recommended.append(name)
        missing = [name for name in required if name.casefold() not in supplied_names]
        return TaxonomyValidation(
            category_id=category_id,
            category_tree_id=tree_id,
            required_aspects=required,
            recommended_aspects=recommended,
            missing_required_aspects=missing,
            supplied_aspects=supplied,
        )

    def listing_preview(self, db: Session, *, listing_id: int) -> dict[str, Any]:
        listing, inventory = self._load_listing_inventory(db, listing_id)
        base_errors = self.validate_inventory_for_ebay(db, inventory)
        taxonomy: TaxonomyValidation | None = None
        taxonomy_error: str | None = None
        if self.connection_status()["connected"]:
            try:
                taxonomy = self.validate_taxonomy(db, listing_id=listing_id)
                base_errors.extend([f"Missing required eBay aspect: {name}" for name in taxonomy.missing_required_aspects])
            except EbayError as exc:
                taxonomy_error = str(exc)
        else:
            taxonomy_error = "Connect eBay to validate category aspects"
        return {
            "listing": listing,
            "inventory": inventory,
            "category_id": self.get_setting(db, f"ebay.listing.{listing.listing_id}.category_id") or self.listing_settings(db)["category_id"],
            "title": listing.title,
            "description": self.build_description(inventory),
            "price_cents": listing.price_cents,
            "images": sorted(inventory.images, key=lambda image: image.image_order),
            "taxonomy": taxonomy,
            "taxonomy_error": taxonomy_error,
            "errors": base_errors,
            "approved": self.is_approved(db, listing.listing_id),
            "environment": settings.ebay_environment,
        }

    def approve_listing(self, db: Session, *, listing_id: int) -> None:
        listing, _ = self._load_listing_inventory(db, listing_id)
        if listing.status != "PENDING":
            raise EbayError("Sync the eBay offer draft before approving it")
        preview = self.listing_preview(db, listing_id=listing_id)
        if preview["errors"]:
            raise EbayError("Cannot approve listing: " + "; ".join(preview["errors"]))
        if preview["taxonomy_error"]:
            raise EbayError("Cannot approve listing until taxonomy validation succeeds")
        self.set_approved(db, listing_id, True)
        db.flush()

    def publish_offer_sandbox(self, db: Session, *, listing_id: int) -> str:
        if not settings.ebay_is_sandbox:
            raise EbayError("v0.6 publication is Sandbox-only. Production publishing is intentionally blocked.")
        listing, inventory = self._load_listing_inventory(db, listing_id)
        if listing.status != "PENDING" or not listing.external_offer_id:
            raise EbayError("Listing must have a synchronized unpublished eBay offer before publishing")
        if not self.is_approved(db, listing_id):
            raise EbayError("Listing must be explicitly approved on the preview screen before publishing")
        result = self.request("POST", f"/sell/inventory/v1/offer/{quote(listing.external_offer_id, safe='')}/publish")
        listing_id_external = str(result.get("listingId") or "")
        if not listing_id_external:
            raise EbayError("eBay publishOffer did not return a listing ID")
        before_status = inventory.status
        listing.external_listing_id = listing_id_external
        listing.status = "ACTIVE"
        listing.listed_at = utcnow()
        listing.ended_at = None
        listing.last_error = None
        inventory.status = InventoryStatus.EBAY_LISTED.value
        db.add(InventoryEvent(
            inventory_id=inventory.inventory_id,
            event_type="EBAY_SANDBOX_PUBLISHED",
            from_status=before_status,
            to_status=inventory.status,
            quantity_delta=0,
            marketplace="EBAY",
            reference_type="LISTING",
            reference_id=listing.listing_id,
            message=f"Published Sandbox offer {listing.external_offer_id} as listing {listing_id_external}",
        ))
        db.flush()
        return listing_id_external

    def withdraw_offer_sandbox(self, db: Session, *, listing_id: int) -> None:
        if not settings.ebay_is_sandbox:
            raise EbayError("v0.6 withdraw control is Sandbox-only")
        listing, inventory = self._load_listing_inventory(db, listing_id)
        if listing.status != "ACTIVE" or not listing.external_offer_id:
            raise EbayError("Only an active Sandbox listing can be withdrawn")
        self.request("POST", f"/sell/inventory/v1/offer/{quote(listing.external_offer_id, safe='')}/withdraw")
        before_status = inventory.status
        listing.status = "PENDING"
        listing.ended_at = utcnow()
        inventory.status = InventoryStatus.EBAY_QUEUE.value
        self.set_approved(db, listing_id, False)
        db.add(InventoryEvent(
            inventory_id=inventory.inventory_id,
            event_type="EBAY_SANDBOX_WITHDRAWN",
            from_status=before_status,
            to_status=inventory.status,
            quantity_delta=0,
            marketplace="EBAY",
            reference_type="LISTING",
            reference_id=listing.listing_id,
            message=f"Withdrew Sandbox offer {listing.external_offer_id}; offer retained unpublished",
        ))
        db.flush()
