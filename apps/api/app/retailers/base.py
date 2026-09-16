"""Retailer product-provider abstraction.

Each retailer speaks its own affiliate/partner API; every adapter maps into
this one `RawProduct` shape and the ingestion service (see
services/product_ingestion_service.py) normalizes + upserts it — search,
the stylist, and try-on never know or care which retailer a product came
from beyond its display name and affiliate link.

Nothing outside this package imports a specific retailer by name; callers
go through `app/retailers/registry.py`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class RawProduct:
    retailer_product_id: str
    name: str
    price_cents: int
    product_url: str
    images: list[str]
    currency: str = "usd"
    brand: str | None = None
    category_slug: str | None = None
    subcategory: str | None = None
    gender: str = "unisex"
    color: str | None = None
    sizes: list[str] = field(default_factory=list)
    description: str | None = None
    rating: float | None = None
    rating_count: int = 0
    availability: str = "in_stock"
    style_tags: list[str] = field(default_factory=list)
    # For aggregator networks where the network itself isn't the seller
    # (Rakuten, CJ) — the actual merchant/advertiser behind the product,
    # distinct from `brand`. None for direct retailers (eBay, Amazon, ...)
    # where the retailer IS the seller.
    merchant_name: str | None = None
    merchant_id: str | None = None


class ProductProvider(ABC):
    #: matches Retailer.slug in the DB — the ingestion service upserts the
    #: Retailer row for this slug automatically if it doesn't exist yet.
    slug: str
    display_name: str

    @abstractmethod
    async def fetch_products(self, *, limit: int = 100) -> list[RawProduct]:
        """Return normalized products from this retailer's feed/API."""
        ...

    async def search_live(self, *, query: str, limit: int = 24) -> list[RawProduct]:
        """On-demand search for one arbitrary user query, fetched fresh at
        request time — never from a pre-synced local catalog. Optional:
        a provider that doesn't (yet) support live per-query search raises
        NotImplementedError rather than silently returning nothing, so
        live_search_service can tell "no results" apart from "can't ask
        this retailer that way."""
        raise NotImplementedError(f"{self.slug} does not support live search")

    def build_affiliate_url(self, product_url: str, *, tracking_tag: str) -> str:
        """Default: append a generic affiliate/tracking query param. Real
        retailer adapters override this with their program's exact scheme
        (Amazon tag=, eBay campid=, impact/CJ/Awin sub-ids, ...)."""
        sep = "&" if "?" in product_url else "?"
        return f"{product_url}{sep}tag={tracking_tag}"
