from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.enums import InventoryStatus
from app.models import AppSetting, Card, InventoryEvent, InventoryItem, Listing, ListingItem
from app.models.base import utcnow


EBAY_SCOPES = (
    "https://api.ebay.com/oauth/api_scope/sell.account",
    "https://api.ebay.com/oauth/api_scope/sell.inventory",
    "https://api.ebay.com/oauth/api_scope/sell.fulfillment",
)

SETTING_PAYMENT_POLICY = "ebay.payment_policy_id"
SETTING_FULFILLMENT_POLICY = "ebay.fulfillment_policy_id"
SETTING_RETURN_POLICY = "ebay.return_policy_id"
SETTING_LOCATION_KEY = "ebay.merchant_location_key"
SETTING_CATEGORY_ID = "ebay.default_category_id"

GRADER_IDS = {
    "PSA": "275010",
    "BCCG": "275011",
    "BVG": "275012",
    "BGS": "275013",
    "CGC": "275015",
    "SGC": "275016",
    "KSA": "275017",
    "GMA": "275018",
    "HGA": "275019",
    "ISA": "2750110",
    "PCA": "2750111",
    "GSG": "2750112",
    "PGS": "2750113",
    "MNT": "2750114",
    "TAG": "2750115",
    "RARE": "2750116",
    "RCG": "2750117",
    "PCG": "2750118",
    "ACE": "2750119",
    "CGA": "2750120",
    "TCG": "2750121",
    "ARK": "2750122",
    "OTHER": "2750123",
}

GRADE_IDS = {
    "10": "275020", "9.5": "275021", "9": "275022", "8.5": "275023",
    "8": "275024", "7.5": "275025", "7": "275026", "6.5": "275027",
    "6": "275028", "5.5": "275029", "5": "2750210", "4.5": "2750211",
    "4": "2750212", "3.5": "2750213", "3": "2750214", "2.5": "2750215",
    "2": "2750216", "1.5": "2750217", "1": "2750218",
    "AUTHENTIC": "2750219", "AUTHENTIC ALTERED": "2750220",
    "AUTHENTIC - TRIMMED": "2750221", "AUTHENTIC - COLOURED": "2750222",
}

UNGRADED_CONDITION_IDS = {
    "NM": "400010",
    "LP": "400015",
    "MP": "400016",
    "HP": "400017",
    "DMG": "400017",
}


class EbayError(RuntimeError):
    pass


@dataclass(slots=True)
class EbayAccountSnapshot:
    privileges: dict[str, Any]
    programs: list[dict[str, Any]]
    payment_policies: list[dict[str, Any]]
    fulfillment_policies: list[dict[str, Any]]
    return_policies: list[dict[str, Any]]
    locations: list[dict[str, Any]]

    @property
    def policy_management_enabled(self) -> bool:
        return any(p.get("programType") == "SELLING_POLICY_MANAGEMENT" for p in self.programs)


@dataclass(slots=True)
class EbayListingResult:
    sku: str
    external_listing_id: str | None = None
    external_offer_id: str | None = None
    listing_url: str | None = None


class EbayService:
    def __init__(self, *, timeout: float = 30.0):
        self.timeout = timeout
        self.token_path = settings.data_dir / "ebay_oauth.json"
        self.state_path = settings.data_dir / "ebay_oauth_state.json"

    @property
    def api_base(self) -> str:
        return "https://api.sandbox.ebay.com" if settings.ebay_is_sandbox else "https://api.ebay.com"

    @property
    def auth_base(self) -> str:
        return "https://auth.sandbox.ebay.com" if settings.ebay_is_sandbox else "https://auth.ebay.com"

    def _require_config(self) -> None:
        if not settings.ebay_configured:
            raise EbayError("eBay is not configured. Set EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, and EBAY_RUNAME in .env.")
        if settings.ebay_environment not in {"sandbox", "production"}:
            raise EbayError("EBAY_ENVIRONMENT must be sandbox or production")

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_private_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            os.chmod(temp, 0o600)
        except OSError:
            pass
        temp.replace(path)

    def connection_status(self) -> dict[str, Any]:
        token = self._load_json(self.token_path)
        expires_at = token.get("expires_at")
        return {
            "configured": settings.ebay_configured,
            "connected": bool(token.get("refresh_token") or token.get("access_token")),
            "environment": settings.ebay_environment,
            "marketplace_id": settings.ebay_marketplace_id,
            "expires_at": expires_at,
            "has_refresh_token": bool(token.get("refresh_token")),
        }

    def begin_authorization(self) -> str:
        self._require_config()
        state = secrets.token_urlsafe(32)
        self._write_private_json(self.state_path, {
            "state": state,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "environment": settings.ebay_environment,
        })
        query = urlencode({
            "client_id": settings.ebay_client_id,
            "response_type": "code",
            "redirect_uri": settings.ebay_runame,
            "scope": " ".join(EBAY_SCOPES),
            "state": state,
            "locale": settings.ebay_locale,
        })
        return f"{self.auth_base}/oauth2/authorize?{query}"

    def _validate_state(self, state: str) -> None:
        pending = self._load_json(self.state_path)
        if not pending or not secrets.compare_digest(str(pending.get("state", "")), state or ""):
            raise EbayError("Invalid or expired eBay OAuth state")
        try:
            created = datetime.fromisoformat(str(pending["created_at"]))
        except (KeyError, ValueError):
            raise EbayError("Invalid eBay OAuth state record")
        if datetime.now(timezone.utc) - created > timedelta(minutes=15):
            raise EbayError("eBay OAuth state expired; start the connection again")
        if pending.get("environment") != settings.ebay_environment:
            raise EbayError("eBay OAuth environment changed during authorization")

    def complete_authorization(self, *, code: str, state: str) -> dict[str, Any]:
        self._require_config()
        self._validate_state(state)
        token = self._token_request({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.ebay_runame,
        })
        self._save_token(token, preserve_refresh=False)
        self.state_path.unlink(missing_ok=True)
        return token

    def _token_request(self, data: dict[str, str]) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.api_base}/identity/v1/oauth2/token",
                    auth=(settings.ebay_client_id, settings.ebay_client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data=data,
                )
        except httpx.HTTPError as exc:
            raise EbayError(f"eBay OAuth request failed: {exc}") from exc
        if response.status_code >= 400:
            raise EbayError(self._error_text(response, prefix="eBay OAuth error"))
        return response.json()

    def _save_token(self, token: dict[str, Any], *, preserve_refresh: bool) -> None:
        existing = self._load_json(self.token_path) if preserve_refresh else {}
        refresh = token.get("refresh_token") or existing.get("refresh_token")
        expires_in = int(token.get("expires_in", 0) or 0)
        payload = {
            "environment": settings.ebay_environment,
            "access_token": token.get("access_token"),
            "refresh_token": refresh,
            "token_type": token.get("token_type"),
            "scope": token.get("scope") or existing.get("scope") or " ".join(EBAY_SCOPES),
            "obtained_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 60, 0))).isoformat(),
        }
        self._write_private_json(self.token_path, payload)

    def _access_token(self, *, force_refresh: bool = False) -> str:
        self._require_config()
        token = self._load_json(self.token_path)
        access_token = token.get("access_token")
        expires_at = token.get("expires_at")
        if access_token and expires_at and not force_refresh:
            try:
                if datetime.now(timezone.utc) < datetime.fromisoformat(expires_at):
                    return str(access_token)
            except ValueError:
                pass
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise EbayError("eBay is not connected or the User token has expired without a refresh token")
        refreshed = self._token_request({
            "grant_type": "refresh_token",
            "refresh_token": str(refresh_token),
            "scope": " ".join(EBAY_SCOPES),
        })
        self._save_token(refreshed, preserve_refresh=True)
        return str(refreshed["access_token"])

    def disconnect(self) -> None:
        self.token_path.unlink(missing_ok=True)
        self.state_path.unlink(missing_ok=True)

    def _error_text(self, response: httpx.Response, *, prefix: str = "eBay API error") -> str:
        try:
            payload = response.json()
        except ValueError:
            return f"{prefix} HTTP {response.status_code}: {response.text[:500]}"
        messages: list[str] = []
        for error in payload.get("errors", []) if isinstance(payload, dict) else []:
            message = error.get("longMessage") or error.get("message")
            if message:
                messages.append(str(message))
        if not messages and isinstance(payload, dict):
            message = payload.get("error_description") or payload.get("message") or payload.get("error")
            if message:
                messages.append(str(message))
        return f"{prefix} HTTP {response.status_code}: " + ("; ".join(messages) or str(payload)[:500])

    def request(self, method: str, path: str, *, params: dict[str, Any] | None = None,
                json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._access_token()
        for attempt in range(2):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.request(
                        method,
                        f"{self.api_base}{path}",
                        params=params,
                        json=json_body,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                            "Content-Language": settings.ebay_locale,
                            "X-EBAY-C-MARKETPLACE-ID": settings.ebay_marketplace_id,
                        },
                    )
            except httpx.HTTPError as exc:
                raise EbayError(f"eBay API request failed: {exc}") from exc
            if response.status_code == 401 and attempt == 0:
                token = self._access_token(force_refresh=True)
                continue
            if response.status_code >= 400:
                raise EbayError(self._error_text(response))
            if response.status_code == 204 or not response.content:
                return {}
            return response.json()
        raise EbayError("eBay authentication failed after token refresh")

    def get_account_snapshot(self) -> EbayAccountSnapshot:
        marketplace = settings.ebay_marketplace_id
        privileges = self.request("GET", "/sell/account/v1/privilege")
        programs_payload = self.request("GET", "/sell/account/v1/program/get_opted_in_programs")
        payments = self.request("GET", "/sell/account/v1/payment_policy", params={"marketplace_id": marketplace})
        fulfillment = self.request("GET", "/sell/account/v1/fulfillment_policy", params={"marketplace_id": marketplace})
        returns = self.request("GET", "/sell/account/v1/return_policy", params={"marketplace_id": marketplace})
        locations = self.request("GET", "/sell/inventory/v1/location", params={"limit": 100})
        return EbayAccountSnapshot(
            privileges=privileges,
            programs=programs_payload.get("programs", []),
            payment_policies=payments.get("paymentPolicies", []),
            fulfillment_policies=fulfillment.get("fulfillmentPolicies", []),
            return_policies=returns.get("returnPolicies", []),
            locations=locations.get("locations", []),
        )

    @staticmethod
    def get_setting(db: Session, key: str, default: str = "") -> str:
        row = db.get(AppSetting, key)
        return row.setting_value if row else default

    @staticmethod
    def set_setting(db: Session, key: str, value: str) -> None:
        row = db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(setting_key=key, setting_value=value, data_type="string"))
        else:
            row.setting_value = value

    def listing_settings(self, db: Session) -> dict[str, str]:
        return {
            "payment_policy_id": self.get_setting(db, SETTING_PAYMENT_POLICY),
            "fulfillment_policy_id": self.get_setting(db, SETTING_FULFILLMENT_POLICY),
            "return_policy_id": self.get_setting(db, SETTING_RETURN_POLICY),
            "merchant_location_key": self.get_setting(db, SETTING_LOCATION_KEY),
            "category_id": self.get_setting(db, SETTING_CATEGORY_ID, settings.ebay_default_category_id),
        }

    def save_listing_settings(self, db: Session, *, payment_policy_id: str, fulfillment_policy_id: str,
                              return_policy_id: str, merchant_location_key: str, category_id: str) -> None:
        self.set_setting(db, SETTING_PAYMENT_POLICY, payment_policy_id.strip())
        self.set_setting(db, SETTING_FULFILLMENT_POLICY, fulfillment_policy_id.strip())
        self.set_setting(db, SETTING_RETURN_POLICY, return_policy_id.strip())
        self.set_setting(db, SETTING_LOCATION_KEY, merchant_location_key.strip())
        self.set_setting(db, SETTING_CATEGORY_ID, category_id.strip())

    @staticmethod
    def build_title(inventory: InventoryItem) -> str:
        card = inventory.card
        if not card:
            return inventory.sku[:80]
        parts = [card.name, card.card_number]
        if card.card_set:
            parts.append(card.card_set.name)
        if card.rarity:
            parts.append(card.rarity)
        if inventory.is_graded and inventory.grading_company and inventory.grade:
            parts.append(f"{inventory.grading_company} {inventory.grade}")
        return " - ".join(str(p) for p in parts if p)[:80]

    @staticmethod
    def build_description(inventory: InventoryItem) -> str:
        card = inventory.card
        lines = [f"SKU: {inventory.sku}"]
        if card:
            lines.append(f"Card: {card.name} {card.card_number}")
            if card.card_set:
                lines.append(f"Set: {card.card_set.name}")
            if card.rarity:
                lines.append(f"Rarity: {card.rarity}")
        lines.append(f"Condition: {inventory.condition or 'Unspecified'}")
        if inventory.variant_label:
            lines.append(f"Variant: {inventory.variant_label}")
        if inventory.is_graded:
            lines.append(f"Grade: {inventory.grading_company or ''} {inventory.grade or ''}".strip())
            if inventory.cert_number:
                lines.append(f"Certification: {inventory.cert_number}")
        return "\n".join(lines)

    @staticmethod
    def _condition_payload(inventory: InventoryItem) -> tuple[str, list[dict[str, Any]]]:
        if inventory.is_graded:
            grader = (inventory.grading_company or "").strip().upper()
            grade = (inventory.grade or "").strip().upper()
            if grader not in GRADER_IDS:
                raise EbayError(f"Unsupported eBay trading-card grader mapping: {grader or 'blank'}")
            if grade not in GRADE_IDS:
                raise EbayError(f"Unsupported eBay trading-card grade mapping: {grade or 'blank'}")
            descriptors: list[dict[str, Any]] = [
                {"name": "27501", "values": [GRADER_IDS[grader]]},
                {"name": "27502", "values": [GRADE_IDS[grade]]},
            ]
            if inventory.cert_number:
                descriptors.append({"name": "27503", "additionalInfo": inventory.cert_number[:30]})
            return "LIKE_NEW", descriptors
        condition = (inventory.condition or "NM").upper()
        descriptor = UNGRADED_CONDITION_IDS.get(condition)
        if not descriptor:
            raise EbayError(f"Unsupported eBay ungraded card condition mapping: {condition}")
        return "USED_VERY_GOOD", [{"name": "40001", "values": [descriptor]}]

    @staticmethod
    def _product_aspects(inventory: InventoryItem) -> dict[str, list[str]]:
        card = inventory.card
        aspects: dict[str, list[str]] = {"Game": ["Pokémon TCG"]}
        if card:
            aspects["Card Name"] = [card.name]
            aspects["Card Number"] = [card.card_number]
            if card.card_set:
                aspects["Set"] = [card.card_set.name]
            if card.rarity:
                aspects["Rarity"] = [card.rarity]
        language_map = {"EN": "English", "JP": "Japanese", "JA": "Japanese"}
        aspects["Language"] = [language_map.get(inventory.language.upper(), inventory.language)]
        return aspects

    @staticmethod
    def _image_urls(inventory: InventoryItem) -> list[str]:
        return [
            image.external_url for image in sorted(inventory.images, key=lambda i: i.image_order)
            if image.external_url and image.external_url.startswith("https://")
        ][:12]

    def validate_inventory_for_ebay(self, db: Session, inventory: InventoryItem, *, category_id: str | None = None) -> list[str]:
        errors: list[str] = []
        if inventory.status != InventoryStatus.EBAY_QUEUE.value:
            errors.append("Inventory is not in EBAY_QUEUE")
        if inventory.quantity_on_hand < 1:
            errors.append("Inventory quantity on hand is zero")
        if not inventory.card:
            errors.append("Inventory is not linked to a card catalog record")
        if not self._image_urls(inventory):
            errors.append("At least one actual inventory image with an HTTPS external URL is required")
        configured = self.listing_settings(db)
        if not (category_id or configured["category_id"]):
            errors.append("eBay category ID is not configured")
        for key, label in (
            ("payment_policy_id", "payment policy"),
            ("fulfillment_policy_id", "fulfillment policy"),
            ("return_policy_id", "return policy"),
            ("merchant_location_key", "inventory location"),
        ):
            if not configured[key]:
                errors.append(f"eBay {label} is not selected")
        try:
            self._condition_payload(inventory)
        except EbayError as exc:
            errors.append(str(exc))
        return errors

    def create_local_draft(self, db: Session, *, inventory: InventoryItem, title: str,
                           price_cents: int, category_id: str) -> Listing:
        if inventory.status != InventoryStatus.EBAY_QUEUE.value:
            raise EbayError("Only EBAY_QUEUE inventory can be drafted for eBay")
        if price_cents <= 0:
            raise EbayError("eBay draft price must be greater than zero")
        existing = db.scalar(
            select(Listing).join(ListingItem).where(
                Listing.marketplace == "EBAY",
                ListingItem.inventory_id == inventory.inventory_id,
                Listing.status.in_(["DRAFT", "PENDING", "ACTIVE"]),
            ).order_by(Listing.listing_id.desc()).limit(1)
        )
        if existing:
            if existing.status == "ACTIVE":
                raise EbayError("This inventory item already has an active eBay listing")
            existing.title = title.strip()[:80] or self.build_title(inventory)
            existing.price_cents = price_cents
            return existing
        listing = Listing(
            marketplace="EBAY",
            listing_type="FIXED_PRICE",
            title=title.strip()[:80] or self.build_title(inventory),
            price_cents=price_cents,
            minimum_offer_cents=inventory.minimum_price_cents,
            quantity=inventory.quantity_on_hand,
            status="DRAFT",
        )
        db.add(listing)
        db.flush()
        db.add(ListingItem(listing_id=listing.listing_id, inventory_id=inventory.inventory_id,
                           quantity=inventory.quantity_on_hand))
        self.set_setting(db, f"ebay.listing.{listing.listing_id}.category_id", category_id.strip())
        db.add(InventoryEvent(
            inventory_id=inventory.inventory_id,
            event_type="EBAY_DRAFT_CREATED",
            from_status=inventory.status,
            to_status=inventory.status,
            quantity_delta=0,
            marketplace="EBAY",
            reference_type="LISTING",
            reference_id=listing.listing_id,
            message="Created local eBay draft",
        ))
        db.flush()
        return listing

    def _load_listing_inventory(self, db: Session, listing_id: int) -> tuple[Listing, InventoryItem]:
        listing = db.scalar(
            select(Listing).where(Listing.listing_id == listing_id).options(
                joinedload(Listing.items).joinedload(ListingItem.inventory_item)
                .joinedload(InventoryItem.card).joinedload(Card.card_set),
                joinedload(Listing.items).joinedload(ListingItem.inventory_item)
                .joinedload(InventoryItem.images),
            )
        )
        if not listing or listing.marketplace != "EBAY" or len(listing.items) != 1:
            raise EbayError("eBay draft not found or unsupported multi-item draft")
        return listing, listing.items[0].inventory_item

    def sync_draft_to_ebay(self, db: Session, *, listing_id: int) -> EbayListingResult:
        listing, inventory = self._load_listing_inventory(db, listing_id)
        category_id = self.get_setting(db, f"ebay.listing.{listing.listing_id}.category_id") or self.listing_settings(db)["category_id"]
        errors = self.validate_inventory_for_ebay(db, inventory, category_id=category_id)
        if errors:
            raise EbayError("; ".join(errors))
        selected = self.listing_settings(db)
        condition, descriptors = self._condition_payload(inventory)
        product = {
            "title": listing.title[:80],
            "description": self.build_description(inventory),
            "aspects": self._product_aspects(inventory),
            "imageUrls": self._image_urls(inventory),
        }
        inventory_payload = {
            "availability": {"shipToLocationAvailability": {"quantity": inventory.quantity_on_hand}},
            "condition": condition,
            "conditionDescriptors": descriptors,
            "product": product,
        }
        self.request("PUT", f"/sell/inventory/v1/inventory_item/{quote(inventory.sku, safe='')}", json_body=inventory_payload)

        offer_payload = {
            "sku": inventory.sku,
            "marketplaceId": settings.ebay_marketplace_id,
            "format": "FIXED_PRICE",
            "availableQuantity": inventory.quantity_on_hand,
            "categoryId": category_id,
            "merchantLocationKey": selected["merchant_location_key"],
            "listingDuration": "GTC",
            "listingPolicies": {
                "paymentPolicyId": selected["payment_policy_id"],
                "fulfillmentPolicyId": selected["fulfillment_policy_id"],
                "returnPolicyId": selected["return_policy_id"],
            },
            "pricingSummary": {"price": {"value": f"{listing.price_cents / 100:.2f}", "currency": "USD"}},
        }
        if listing.external_offer_id:
            self.request("PUT", f"/sell/inventory/v1/offer/{listing.external_offer_id}", json_body=offer_payload)
            offer_id = listing.external_offer_id
        else:
            result = self.request("POST", "/sell/inventory/v1/offer", json_body=offer_payload)
            offer_id = str(result.get("offerId") or "")
            if not offer_id:
                raise EbayError("eBay created the inventory item but did not return an offer ID")
            listing.external_offer_id = offer_id

        listing.status = "PENDING"
        listing.last_synced_at = utcnow()
        listing.last_error = None
        db.add(InventoryEvent(
            inventory_id=inventory.inventory_id,
            event_type="EBAY_DRAFT_SYNCED",
            from_status=inventory.status,
            to_status=inventory.status,
            quantity_delta=0,
            marketplace="EBAY",
            reference_type="LISTING",
            reference_id=listing.listing_id,
            message=f"Synced eBay offer draft {offer_id}; not published",
        ))
        db.flush()
        return EbayListingResult(sku=inventory.sku, external_offer_id=offer_id)
