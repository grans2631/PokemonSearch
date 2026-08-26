"""eBay integration boundary.

v0.1 intentionally leaves network/API actions unimplemented.  Future code should
keep OAuth and eBay payload mapping in this module rather than leaking marketplace
objects throughout the domain model.
"""

from dataclasses import dataclass


@dataclass(slots=True)
class EbayListingResult:
    sku: str
    external_listing_id: str
    external_offer_id: str | None = None
    listing_url: str | None = None


class EbayService:
    def create_listing(self, *, inventory_id: int) -> EbayListingResult:
        raise NotImplementedError("eBay listing creation is planned for v0.2")

    def sync_orders(self) -> int:
        raise NotImplementedError("eBay order synchronization is planned for v0.2")
